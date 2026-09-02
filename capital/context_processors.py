"""
Context processor: inyecta el balance paralelo formateado en el navbar.

Solo para usuarios autenticados con modo compuesto activado (balance
declarado + ancla). El navbar muestra SOLO el número con signo $ (sin
etiqueta de "balance", por decisión de John 2026-09-01).
"""

from .services import bankroll_cop, format_cop, get_config


def navbar_balance(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    try:
        cfg = get_config(user)
        if cfg.balance_inicial is None or cfg.ancla is None:
            return {'navbar_balance': None, 'navbar_balance_negativo': False}
        balance = bankroll_cop(user)
    except Exception:
        # Nunca romper la renderización de la página por el balance.
        return {}

    if balance is None:
        return {'navbar_balance': None, 'navbar_balance_negativo': False}
    return {
        'navbar_balance': format_cop(balance),
        'navbar_balance_negativo': balance < 0,
    }
