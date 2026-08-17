from enum import StrEnum


class TransactionType(StrEnum):
    """Natureza do lançamento: entrada ou saída de recursos."""
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class TransactionStatus(StrEnum):
    """Estado contábil do lançamento, base da separação de regimes"""

    # Compõe exclusivamente o regime de competência.
    PENDING = "PENDING"

    # Compõe o regime de caixa.
    SETTLED = "SETTLED"

    # Não compõe nenhum dos regimes: permanece persistido apenas como rastro de auditoria.
    CANCELED = "CANCELED"
