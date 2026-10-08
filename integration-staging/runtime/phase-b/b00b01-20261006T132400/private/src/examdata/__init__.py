"""Private candidate parent package (B01 layout validation).

This shim exists only so `examdata.integration` can be imported from the
private tree during layout validation. It is not the original package and
carries no original code.
"""

__all__ = ["integration"]
