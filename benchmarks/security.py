import subprocess

SUPPORTED_LANGUAGES = {"python"}
import json
import os
import time
import logging
import tempfile
from typing import List, Dict, Any, Iterable, Callable, Optional
from urllib.parse import urlparse
from .utils import get_python_files
from .stats_utils import BenchmarkResult, calculate_confidence_interval, adjust_score_for_size, get_codebase_size_bucket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _safe_json_loads(text: str) -> Optional[Any]:
    """Safely parse JSON text returning None on parse errors."""
    try:
        return json.loads(text)
    except Exception:
        return None

def _format_issue_lines(items: Iterable[Any], formatter: Callable[[Any], str], limit: Optional[int] = None) -> List[str]:
    """
    Format an iterable of items into a list of strings using the provided formatter.
    Uses a generator-like approach to avoid building intermediate large lists; supports an optional limit.
    """
    lines: List[str] = []
    if limit is None or limit < 0:
        iterator = items
    else:
        def limited(it: Iterable[Any], n: int):
            i = 0
            for x in it:
                if i >= n:
                    break
                yield x
                i += 1
        iterator = limited(items, limit)
    for item in iterator:
        lines.append(formatter(item))
    return lines

def _count_keywords(text: str, keywords: Iterable[str]) -> Dict[str, int]:
    """Count occurrences of multiple keywords in text and return a dictionary of counts."""
    return {k: text.count(k) for k in keywords}

def assess_security(codebase_path: str) -> BenchmarkResult:
    """
    Hybrid static + dynamic security assessment.
    Combines bandit/safety with optional OWASP ZAP dynamic scanning.
    """
    details = []
    raw_metrics = {}
    
    # === STATIC ANALYSIS ===
    static_score, static_details, static_metrics = _assess_static_security(codebase_path)
    details.extend(static_details)
    raw_metrics.update(static_metrics)
    
    # === DYNAMIC ANALYSIS ===
    web_app_url = os.getenv("BENCH_WEB_APP_URL")  # e.g., http://localhost:8000
    if web_app_url:
        dynamic_score, dynamic_details, dynamic_metrics = _assess_dynamic_security(web_app_url)
        details.extend(dynamic_details)
        raw_metrics.update(dynamic_metrics)
        
        # Combine static + dynamic (weighted)
        final_score = (0.6 * static_score) + (0.4 * dynamic_score)
    else:
        final_score = static_score
        details.append("No web app URL provided (set BENCH_WEB_APP_URL). Using static analysis only.")
    
    # === BIAS ADJUSTMENT ===
    size_bucket = get_codebase_size_bucket(codebase_path)
    adjusted_score = adjust_score_for_size(final_score, size_bucket, "security")
    raw_metrics["size_bucket"] = size_bucket
    raw_metrics["unadjusted_score"] = final_score
    
    # === CONFIDENCE INTERVAL ===
    score_samples = [static_score]
    if "dynamic_score" in raw_metrics:
        score_samples.append(raw_metrics["dynamic_score"])
    
    confidence_interval = calculate_confidence_interval(score_samples)
    
    return BenchmarkResult(
        score=adjusted_score,
        details=details,
        raw_metrics=raw_metrics,
        confidence_interval=confidence_interval
    )


def _assess_static_security(codebase_path: str) -> tuple[float, List[str], Dict[str, Any]]:
    """Static security analysis with bandit and safety."""
    details = []
    metrics = {}
    
    # --- Bandit Scan ---
    bandit_score = 10.0
    try:
        logger.info("Starting Bandit scan for path: %s", codebase_path)
        command = [
            "bandit", "-r", codebase_path, "-f", "json",
            "--skip", "B101,B601",  # Skip common test-related issues
            "--exclude", "*/stls/*,*/dataset.zip,*/.venv/*,*/node_modules/*,*/__pycache__/*,*/build/*,*/dist/*,*.pyc,*.zip,*.tar.gz,*.stl,*.step,*.blob,*.pdf,*.png,*.jpg,*.wav,*.mp3"
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
        report = json.loads(result.stdout) if result.stdout else {}
        
        if report and "results" in report:
            findings = report["results"]
            high = sum(1 for f in findings if f.get("issue_severity") == "HIGH")
            medium = sum(1 for f in findings if f.get("issue_severity") == "MEDIUM")
            low = sum(1 for f in findings if f.get("issue_severity") == "LOW")
            
            details.append(f"[Bandit] High: {high}, Medium: {medium}, Low: {low}")
            metrics["bandit_high"] = high
            metrics["bandit_medium"] = medium
            metrics["bandit_low"] = low

            # Use helper to format findings (generator-friendly)
            details.extend(_format_issue_lines(
                (f for f in findings),
                lambda f: f"  - {f.get('issue_text')} ({f.get('filename')}:{f.get('line_number')})",
                limit=10
            ))

            score_deduction = (high * 3) + (medium * 1) + (low * 0.5)
            bandit_score = max(0.0, 10.0 - score_deduction)
        else:
            details.append("[Bandit] No report generated or empty output")
            logger.info("Bandit produced no JSON output")
            bandit_score = 8.0
    except subprocess.TimeoutExpired:
        details.append("[Bandit] Scan timed out (>60s)")
        logger.error("Bandit scan timed out for path: %s", codebase_path)
        bandit_score = 3.0
    except FileNotFoundError:
        details.append("[Bandit] Could not run bandit (not installed).")
        logger.exception("Bandit executable not found")
        bandit_score = 0.0
    except json.JSONDecodeError:
        details.append("[Bandit] Could not parse bandit output.")
        logger.exception("Failed to parse Bandit JSON output")
        bandit_score = 0.0
    except Exception as e:
        details.append(f"[Bandit] Error: {str(e)[:100]}")
        logger.exception("Unexpected error running Bandit: %s", e)
        bandit_score = 0.0

    # --- Safety Scan ---
    safety_score = 10.0
    req_file = os.path.join(codebase_path, "requirements.txt")
    if os.path.exists(req_file):
        try:
            logger.info("Starting Safety scan for requirements: %s", req_file)
            # Try new safety scan first (requires auth but may work)
            command = ["safety", "scan", "--file", req_file, "--output", "json", "--disable-optional-telemetry"]
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5)
            
            if result.returncode != 0:
                # Fallback: try deprecated safety check
                command = ["safety", "check", f"--file={req_file}", "--json", "--disable-optional-telemetry"]
                result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5)
            
            if result.stdout:
                try:
                    report = json.loads(result.stdout)
                    # Handle both old and new format
                    if isinstance(report, list):
                        vulns = len(report)
                        details.append(f"[Safety] {vulns} vulnerable dependencies")
                        metrics["safety_vulnerabilities"] = vulns
                        
                        # Format top N vulnerabilities using helper
                        details.extend(_format_issue_lines(
                            (v for v in report),
                            lambda vuln: f"  - {vuln.get('package_name', vuln.get('package', 'unknown'))}: {vuln.get('advisory', vuln.get('vulnerability_id', 'No description'))[:100]}...",
                            limit=5
                        ))
                        
                        safety_score = max(0.0, 10.0 - (vulns * 2))
                    else:
                        # New format handling
                        vulns = len(report.get('vulnerabilities', []))
                        details.append(f"[Safety] {vulns} vulnerable dependencies")
                        metrics["safety_vulnerabilities"] = vulns
                        safety_score = max(0.0, 10.0 - (vulns * 2))
                except json.JSONDecodeError:
                    details.append("[Safety] No vulnerabilities detected (could not parse JSON)")
                    logger.exception("Failed to parse Safety JSON output")
                    safety_score = 10.0
            else:
                details.append("[Safety] No output from safety command")
                logger.info("Safety produced no stdout")
                safety_score = 8.0
                
        except subprocess.TimeoutExpired:
            details.append("[Safety] Scan timed out (>5s) - skipping dependency check")
            logger.error("Safety scan timed out for file: %s", req_file)
            safety_score = 7.0  # Neutral score for timeout
        except FileNotFoundError:
            details.append("[Safety] Safety tool not available")
            logger.exception("Safety executable not found")
            safety_score = 8.0  # Neutral if tool unavailable
        except Exception as e:
            details.append(f"[Safety] Error: {str(e)[:100]}")
            logger.exception("Unexpected error running Safety: %s", e)
            safety_score = 5.0
    else:
        details.append("[Safety] No requirements.txt found.")
        safety_score = 8.0  # Neutral if no deps to check

    # Combine static scores
    static_score = (bandit_score * 0.7) + (safety_score * 0.3)
    metrics["bandit_score"] = bandit_score
    metrics["safety_score"] = safety_score
    
    return static_score, details, metrics


def _assess_dynamic_security(web_app_url: str) -> tuple[float, List[str], Dict[str, Any]]:
    """Dynamic security testing with OWASP ZAP (if available)."""
    details = []
    metrics = {}
    
    # Basic validation of provided URL
    try:
        parsed = urlparse(web_app_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            details.append("[ZAP] Invalid URL provided for dynamic scan")
            logger.error("Invalid WEB_APP_URL provided: %s", web_app_url)
            metrics["dynamic_score"] = 5.0
            return 5.0, details, metrics
    except Exception:
        details.append("[ZAP] Invalid URL provided for dynamic scan")
        logger.exception("Error parsing WEB_APP_URL: %s", web_app_url)
        metrics["dynamic_score"] = 5.0
        return 5.0, details, metrics

    # Check if ZAP is available
    try:
        details.append(f"[ZAP] Running baseline scan on {web_app_url}")
        logger.info("Starting ZAP baseline scan for: %s", web_app_url)
        # Use a secure temporary directory to receive reports from the container
        with tempfile.TemporaryDirectory() as tmpdir:
            host_report_path = os.path.join(tmpdir, "zap-report.json")
            container_report_path = "/zap/reports/zap-report.json"
            command = [
                "docker", "run", "--rm", "-t",
                "-v", f"{tmpdir}:/zap/reports:Z",
                "owasp/zap2docker-stable",
                "zap-baseline.py",
                "-t", web_app_url,
                "-J", container_report_path
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                check=False
            )
            
            # Prefer reading the generated report file if present
            high_count = medium_count = low_count = 0
            try:
                if os.path.exists(host_report_path):
                    with open(host_report_path, "r", encoding="utf-8") as f:
                        report_json = f.read()
                    counts = _count_keywords(report_json, ("HIGH", "MEDIUM", "LOW"))
                    high_count = counts.get("HIGH", 0)
                    medium_count = counts.get("MEDIUM", 0)
                    low_count = counts.get("LOW", 0)
                else:
                    # Fallback: inspect stdout for severity keywords
                    out = result.stdout or ""
                    counts = _count_keywords(out, ("HIGH", "MEDIUM", "LOW"))
                    high_count = counts.get("HIGH", 0)
                    medium_count = counts.get("MEDIUM", 0)
                    low_count = counts.get("LOW", 0)
            except Exception:
                logger.exception("Failed to read or parse ZAP report file")
                out = result.stdout or ""
                counts = _count_keywords(out, ("HIGH", "MEDIUM", "LOW"))
                high_count = counts.get("HIGH", 0)
                medium_count = counts.get("MEDIUM", 0)
                low_count = counts.get("LOW", 0)
            
            if high_count or medium_count or low_count:
                details.append(f"[ZAP] Findings - High: {high_count}, Medium: {medium_count}, Low: {low_count}")
                
                metrics["zap_high"] = high_count
                metrics["zap_medium"] = medium_count
                metrics["zap_low"] = low_count
                
                # Score based on findings
                score_deduction = (high_count * 4) + (medium_count * 2) + (low_count * 0.5)
                dynamic_score = max(0.0, 10.0 - score_deduction)
            else:
                details.append("[ZAP] Scan completed but no findings detected")
                dynamic_score = 8.0
                
    except subprocess.TimeoutExpired:
        details.append("[ZAP] Scan timed out (>2 min)")
        logger.error("ZAP scan timed out for URL: %s", web_app_url)
        dynamic_score = 3.0
    except FileNotFoundError:
        details.append("[ZAP] Docker/ZAP not available. Install: docker pull owasp/zap2docker-stable")
        logger.exception("Docker executable not found or not runnable")
        dynamic_score = 5.0  # Neutral if tool unavailable
    except Exception as e:
        details.append(f"[ZAP] Error: {str(e)}")
        logger.exception("Unexpected error running ZAP: %s", e)
        dynamic_score = 3.0
    
    metrics["dynamic_score"] = dynamic_score
    return dynamic_score, details, metrics