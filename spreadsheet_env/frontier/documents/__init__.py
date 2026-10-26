"""Document-grade frontier tier: the spec is a generated legal document.

Domains (each ``<domain>_build`` / ``_repair`` / ``_free`` x levels 1-5):

    ca         credit agreement (leveraged loan: pricing grid, ECF sweep, revolver,
               netting limit, springing covenant with equity cure, HoldCo PIK)
    lpa        limited partnership agreement (fund distribution waterfall)
    indenture  ABS indenture (monthly priority of payments)
    charter    VC certificate of incorporation (liquidation preference)

Calibration showed that formula-level term sheets are solved by frontier models
however complex the logic; every divergence came from interpretation. These
domains move the difficulty there: the same kind of semantics, drafted the way
the real documents are (alphabetical defined terms, cross-references, provisos,
distractor clauses).
"""

DOC_DOMAINS = ("credit_agreement", "lpa", "indenture", "charter")
