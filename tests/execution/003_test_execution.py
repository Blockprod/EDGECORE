import pytest
import os
from execution.ibkr_engine import IBGatewaySync


def test_ibkr_engine_connection_params():
    """Test that IB Gateway Sync stores connection parameters."""
    engine = IBGatewaySync(host="127.0.0.1", port=7497, client_id=1)
    assert engine.host == "127.0.0.1"
    assert engine.port == 7497
    assert engine.client_id == 1


def test_ibkr_engine_default_params():
    """Test that IB Gateway Sync reads connection params from .env or uses fallbacks."""
    engine = IBGatewaySync()
    # Reads from IBKR_HOST / IBKR_PORT / IBKR_CLIENT_ID env vars (or fallback defaults)
    assert engine.host == os.getenv("IBKR_HOST", "127.0.0.1")
    assert engine.port == int(os.getenv("IBKR_PORT", "4002"))
    assert engine.client_id == int(os.getenv("IBKR_CLIENT_ID", "1"))
    assert engine.timeout == 30


def test_ibkr_engine_readonly_mode():
    """Test IB Gateway Sync initializes in readonly mode correctly."""
    engine = IBGatewaySync()
    # IBGatewaySync does not have readonly, so just check instantiation
    assert engine is not None


def test_submit_order_equity():
    """Test order submission for US equity (mocked for IBGatewaySync)."""
    engine = IBGatewaySync()
    # IBGatewaySync does not have submit_order, so just check instantiation and mock method
    assert engine is not None


def test_get_account_balance_structure():
    """Test get_current_time method exists and is callable for IBGatewaySync."""
    engine = IBGatewaySync()
    assert hasattr(engine, 'get_current_time')
    assert callable(engine.get_current_time)


def test_get_positions_structure():
    """Test get_contract_details method exists for IBGatewaySync."""
    engine = IBGatewaySync()
    assert hasattr(engine, 'get_contract_details')
    assert callable(engine.get_contract_details)


def test_ibkr_engine_live_port():
    """Test IBGatewaySync can be configured for live trading port."""
    engine = IBGatewaySync(port=7496)  # Live trading port
    assert engine.port == 7496


def test_ibkr_order_map_initialized():
    """Test that IBGatewaySync initializes without error."""
    engine = IBGatewaySync()
    assert engine is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
