from dataclasses import dataclass
from enum import Enum

class ConstraintType(Enum):
    """Risk constraint types."""
    POSITION_SIZE = "POSITION_SIZE"
    NOTIONAL_EXPOSURE = "NOTIONAL_EXPOSURE"
    SECTOR_CONCENTRATION = "SECTOR_CONCENTRATION"
    CURRENCY_EXPOSURE = "CURRENCY_EXPOSURE"
    FACTOR_EXPOSURE = "FACTOR_EXPOSURE"

@dataclass
class RiskConstraint:
    """Generic risk constraint."""
    constraint_type: ConstraintType
    limit: float
    current_value: float = 0.0
    
    def is_breached(self) -> bool:
        """Check if constraint is violated."""
        return self.current_value > self.limit
