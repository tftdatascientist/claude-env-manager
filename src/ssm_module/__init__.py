"""SSM — Scripted System Monitor, moduł Claude Manager."""
from .core.ssm_service import SSMService
from .views.ssm_tab import SsmTab

__all__ = ['SsmTab', 'SSMService']
