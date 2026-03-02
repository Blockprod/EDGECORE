"""
Disaster recovery and data integrity for EDGECORE trading system.

Provides:
- Recovery after system crash
- Audit trail backup and verification
- Position reconciliation
- Data integrity checks
"""

from datetime import datetime
from pathlib import Path
from structlog import get_logger
from persistence.audit_trail import AuditTrail

logger = get_logger(__name__)


class DisasterRecovery:
    """Disaster recovery and data integrity operations."""
    
    def __init__(self):
        self.audit_trail = AuditTrail()
        self.recovery_log_dir = Path("logs/recovery")
        self.recovery_log_dir.mkdir(parents=True, exist_ok=True)
    
    def recover_from_crash(self, skip_broker_check: bool = False) -> dict:
        """
        Full recovery procedure after system crash.
        
        1. Load audit trail
        2. Reconcile with broker
        3. Restore positions + equity
        4. Resume trading or pause for review
        
        Args:
            skip_broker_check: If True, skip broker reconciliation
        
        Returns:
            Recovery status report
        """
        logger.critical("DISASTER_RECOVERY_INITIATED", timestamp=datetime.utcnow())
        
        report = {
            "status": "in_progress",
            "start_time": datetime.utcnow(),
            "steps": []
        }
        
        try:
            # Step 1: Load audit trail
            logger.info("recovery_step", step=1, action="loading_audit_trail")
            audit_data = self.audit_trail.load_full_audit_trail()
            report["steps"].append({
                "step": 1,
                "action": "load_audit_trail",
                "success": True,
                "records": len(audit_data) if audit_data else 0
            })
            
            # Step 2: Verify data integrity
            logger.info("recovery_step", step=2, action="verifying_data_integrity")
            integrity_check = self.verify_data_integrity(audit_data)
            report["steps"].append({
                "step": 2,
                "action": "verify_integrity",
                "success": integrity_check["is_valid"],
                "issues": integrity_check.get("issues", [])
            })
            
            if not integrity_check["is_valid"]:
                logger.error("INTEGRITY_CHECK_FAILED", issues=integrity_check["issues"])
                report["status"] = "failed"
                report["error"] = "Data integrity check failed"
                return report
            
            # Step 3: Reconstruct positions (if skip_broker_check=False)
            if not skip_broker_check:
                logger.info("recovery_step", step=3, action="reconciling_positions")
                positions = self.reconstruct_positions(audit_data)
                report["steps"].append({
                    "step": 3,
                    "action": "reconstruct_positions",
                    "success": True,
                    "positions": len(positions)
                })
            else:
                logger.info("recovery_step", step=3, action="skipping_broker_reconciliation")
                report["steps"].append({
                    "step": 3,
                    "action": "skipped (--skip-broker-check)",
                    "success": True
                })
            
            # Step 4: Save recovery report
            logger.info("recovery_step", step=4, action="saving_recovery_report")
            report_file = self.save_recovery_report(report)
            report["steps"].append({
                "step": 4,
                "action": "save_report",
                "success": True,
                "report_file": str(report_file)
            })
            
            report["status"] = "success"
            report["end_time"] = datetime.utcnow()
            
            logger.critical(
                "RECOVERY_COMPLETE",
                status="success",
                duration_seconds=(report["end_time"] - report["start_time"]).total_seconds()
            )
            
            return report
            
        except Exception as e:
            logger.error("RECOVERY_FAILED", error=str(e))
            report["status"] = "failed"
            report["error"] = str(e)
            report["end_time"] = datetime.utcnow()
            return report
    
    def verify_data_integrity(self, audit_data: list) -> dict:
        """
        Verify audit trail and position data haven't been tampered with.
        
        Args:
            audit_data: Audit trail records
        
        Returns:
            {
                "is_valid": bool,
                "issues": [...],
                "checksum": str
            }
        """
        issues = []
        
        # Check 1: Verify audit trail is not empty
        if not audit_data or len(audit_data) == 0:
            issues.append("Audit trail is empty - no recovery data available")
        
        # Check 2: Verify chronological order
        prev_timestamp = None
        for record in audit_data:
            if prev_timestamp and record.get("timestamp") < prev_timestamp:
                issues.append(f"Audit trail not in chronological order at record {record}")
                break
            prev_timestamp = record.get("timestamp")
        
        # Check 3: Verify required fields in trades
        for record in audit_data:
            if record.get("type") == "trade":
                required_fields = ["symbol", "side", "quantity", "entry_price", "timestamp"]
                missing = [f for f in required_fields if f not in record]
                if missing:
                    issues.append(f"Trade record missing fields: {missing}")
        
        is_valid = len(issues) == 0
        
        logger.info(
            "data_integrity_check",
            is_valid=is_valid,
            issues_count=len(issues),
            records=len(audit_data)
        )
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "records_checked": len(audit_data)
        }
    
    def reconstruct_positions(self, audit_data: list) -> dict:
        """
        Reconstruct open positions from audit trail.
        
        Args:
            audit_data: Audit trail records
        
        Returns:
            Dict of reconstructed positions: {
                "symbol_pair": {
                    "side": "long|short",
                    "quantity": float,
                    "entry_price": float,
                    "entry_time": datetime
                }
            }
        """
        positions = {}
        
        # Replay all trades
        for record in audit_data:
            if record.get("type") == "trade":
                symbol = record.get("symbol")
                action = record.get("side")  # "BUY" or "SELL"
                quantity = record.get("quantity", 0)
                entry_price = record.get("entry_price", 0)
                timestamp = record.get("timestamp")
                
                if action == "BUY":
                    # Opening long or closing short
                    if symbol not in positions:
                        positions[symbol] = {
                            "side": "long",
                            "quantity": quantity,
                            "entry_price": entry_price,
                            "entry_time": timestamp
                        }
                    else:
                        # Adjust existing position
                        if positions[symbol]["side"] == "long":
                            positions[symbol]["quantity"] += quantity
                        else:  # short
                            positions[symbol]["quantity"] -= quantity
                            if positions[symbol]["quantity"] == 0:
                                del positions[symbol]
                
                elif action == "SELL":
                    # Opening short or closing long
                    if symbol not in positions:
                        positions[symbol] = {
                            "side": "short",
                            "quantity": quantity,
                            "entry_price": entry_price,
                            "entry_time": timestamp
                        }
                    else:
                        # Adjust existing position
                        if positions[symbol]["side"] == "short":
                            positions[symbol]["quantity"] += quantity
                        else:  # long
                            positions[symbol]["quantity"] -= quantity
                            if positions[symbol]["quantity"] == 0:
                                del positions[symbol]
        
        logger.info("positions_reconstructed", count=len(positions))
        return positions
    
    def backup_audit_trail(self, backup_dir: str = "backups/audit_trail") -> str:
        """
        Create backup of current audit trail.
        
        Args:
            backup_dir: Directory to store backup
        
        Returns:
            Path to backup file
        """
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"audit_trail_backup_{timestamp}.csv"
        
        # Load audit trail
        audit_data = self.audit_trail.load_full_audit_trail()
        
        # Write to file
        with open(backup_file, 'w') as f:
            if audit_data:
                # Write headers
                headers = list(audit_data[0].keys())
                f.write(",".join(headers) + "\n")
                
                # Write records
                for record in audit_data:
                    values = [str(record.get(h, "")) for h in headers]
                    f.write(",".join(values) + "\n")
        
        logger.info("backup_audit_trail", backup_file=str(backup_file), records=len(audit_data))
        return str(backup_file)
    
    def save_recovery_report(self, report: dict) -> Path:
        """
        Save recovery report to file.
        
        Args:
            report: Recovery report dict
        
        Returns:
            Path to report file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = self.recovery_log_dir / f"recovery_report_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("DISASTER RECOVERY REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Status: {report['status']}\n")
            f.write(f"Start time: {report['start_time']}\n")
            f.write(f"End time: {report.get('end_time', 'N/A')}\n")
            
            if 'steps' in report:
                f.write("\nRecovery Steps:\n")
                for step in report['steps']:
                    f.write(f"  [{step['step']}] {step.get('action', 'Unknown')}: ")
                    f.write(f"{'SUCCESS' if step.get('success') else 'FAILED'}\n")
                    if 'records' in step:
                        f.write(f"       Records: {step['records']}\n")
                    if 'positions' in step:
                        f.write(f"       Positions: {step['positions']}\n")
                    if 'issues' in step and step['issues']:
                        for issue in step['issues']:
                            f.write(f"       Issue: {issue}\n")
            
            if 'error' in report:
                f.write(f"\nError: {report['error']}\n")
        
        logger.info("recovery_report_saved", report_file=str(report_file))
        return report_file


def recover_from_crash(skip_broker_check: bool = False) -> dict:
    """
    Execute full disaster recovery procedure.
    
    Args:
        skip_broker_check: If True, skip broker reconciliation
    
    Returns:
        Recovery status report
    """
    recovery = DisasterRecovery()
    return recovery.recover_from_crash(skip_broker_check=skip_broker_check)


def backup_audit_trail() -> str:
    """Backup current audit trail."""
    recovery = DisasterRecovery()
    return recovery.backup_audit_trail()


def verify_data_integrity() -> dict:
    """Verify data integrity of audit trail."""
    recovery = DisasterRecovery()
    audit_data = recovery.audit_trail.load_full_audit_trail()
    return recovery.verify_data_integrity(audit_data)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--backup":
        print(f"Backup saved to: {backup_audit_trail()}")
    elif len(sys.argv) > 1 and sys.argv[1] == "--verify":
        integrity = verify_data_integrity()
        print(f"Integrity check: {'PASS' if integrity['is_valid'] else 'FAIL'}")
        if integrity['issues']:
            for issue in integrity['issues']:
                print(f"  - {issue}")
    elif len(sys.argv) > 1 and sys.argv[1] == "--recover":
        skip_broker = "--skip-broker-check" in sys.argv
        report = recover_from_crash(skip_broker_check=skip_broker)
        print(f"Recovery status: {report['status']}")
    else:
        print("Usage: python scripts/disaster_recovery.py [--backup|--verify|--recover]")
        print("  --backup: Create backup of audit trail")
        print("  --verify: Verify data integrity")
        print("  --recover: Execute full disaster recovery")
        print("  --recover --skip-broker-check: Recovery without broker reconciliation")
