"""知识点体系种子数据。

来源：各科目官方 syllabus 的"Subject content"章节标题（Cambridge 公开 PDF），
以及历年真题的题型分布。这里只做**两层**（topic / subtopic），
不臆造更细的层级——细层级应当来自后续的人工标注与统计。

所有种子节点落库时 source="seed"，人工确认后改为 "manual"，
后续从真题统计自动发现的节点用 "auto"。三者在 TaxonomyNode.source 上区分，
检索时可以只看 official/manual，避免自动结果污染。
"""

from __future__ import annotations

from typing import TypedDict


class SeedNode(TypedDict, total=False):
    code: str
    name: str
    node_type: str
    keywords: list[str]
    children: list["SeedNode"]


# --------------------------------------------------------------------------
# 0580 Mathematics (IGCSE)
# --------------------------------------------------------------------------

_0580: list[SeedNode] = [
    {
        "code": "0580.1",
        "name": "Number",
        "children": [
            {"code": "0580.1.1", "name": "Types of number", "keywords": [
                "prime", "factor", "multiple", "hcf", "lcm", "square", "cube", "root",
                "integer", "rational", "irrational", "recurring", "set", "venn", "element"]},
            {"code": "0580.1.2", "name": "Fractions, decimals and percentages", "keywords": [
                "fraction", "decimal", "percentage", "percent", "%", "convert", "simplest form"]},
            {"code": "0580.1.3", "name": "Powers, roots and standard form", "keywords": [
                "index", "indices", "power", "standard form", "surds", "negative power"]},
            {"code": "0580.1.4", "name": "Estimation and limits of accuracy", "keywords": [
                "estimate", "approximate", "round", "nearest", "significant figures",
                "decimal places", "upper bound", "lower bound", "limits of accuracy", "correct to"]},
            {"code": "0580.1.5", "name": "Ratio, proportion and rates", "keywords": [
                "ratio", "proportion", "direct", "inverse", "rate", "per", "scale",
                "map", "speed", "density", "pressure", "exchange rate", "best buy"]},
            {"code": "0580.1.6", "name": "Money and finance", "keywords": [
                "interest", "simple interest", "compound interest", "discount", "profit",
                "loss", "tax", "salary", "wage", "loan", "investment", "depreciat"]},
            {"code": "0580.1.7", "name": "Time and timetables", "keywords": [
                "time", "hours", "minutes", "timetable", "24-hour", "clock", "duration"]},
        ],
    },
    {
        "code": "0580.2",
        "name": "Algebra and graphs",
        "children": [
            {"code": "0580.2.1", "name": "Algebraic manipulation", "keywords": [
                "simplify", "expand", "bracket", "factorise", "factorize", "collect",
                "substitute", "expression", "like terms", "algebraic fraction"]},
            {"code": "0580.2.2", "name": "Equations and inequalities", "keywords": [
                "solve", "equation", "inequality", "simultaneous", "quadratic",
                "linear equation", "unknown", "formula", "rearrange", "subject"]},
            {"code": "0580.2.3", "name": "Sequences", "keywords": [
                "sequence", "term", "nth term", "arithmetic", "geometric", "pattern", "progression"]},
            {"code": "0580.2.4", "name": "Graphs of functions", "keywords": [
                "graph", "sketch", "curve", "gradient", "intercept", "asymptote",
                "turning point", "maximum", "minimum", "tangent", "derivative",
                "distance-time", "speed-time", "travel graph", "function", "domain", "range",
                "inverse function", "composite"]},
            {"code": "0580.2.5", "name": "Indices and surds in algebra", "keywords": [
                "indices", "power law", "rational exponent", "surd", "rationalise"]},
        ],
    },
    {
        "code": "0580.3",
        "name": "Coordinate geometry",
        "children": [
            {"code": "0580.3.1", "name": "Coordinates and lines", "keywords": [
                "coordinates", "midpoint", "line segment", "length of", "parallel", "perpendicular"]},
            {"code": "0580.3.2", "name": "Gradient and equations of lines", "keywords": [
                "gradient", "slope", "y = mx", "equation of the line", "straight line",
                "passes through", "collinear"]},
        ],
    },
    {
        "code": "0580.4",
        "name": "Geometry",
        "children": [
            {"code": "0580.4.1", "name": "Geometrical terms and angle properties", "keywords": [
                "angle", "triangle", "parallel", "polygon", "interior", "exterior",
                "isosceles", "equilateral", "quadrilateral", "circle theorem",
                "cyclic", "tangent", "chord", "alternate segment", "bearing"]},
            {"code": "0580.4.2", "name": "Symmetry and transformations", "keywords": [
                "symmetry", "line of symmetry", "rotational", "reflection", "rotation",
                "translation", "enlargement", "transformation", "scale factor", "image"]},
            {"code": "0580.4.3", "name": "Constructions and loci", "keywords": [
                "construct", "compasses", "ruler", "locus", "loci", "perpendicular bisector",
                "angle bisector", "scale drawing"]},
            {"code": "0580.4.4", "name": "Similarity and congruence", "keywords": [
                "similar", "congruent", "congruence", "similarity", "scale factor",
                "corresponding", "ratio of areas", "ratio of volumes"]},
        ],
    },
    {
        "code": "0580.5",
        "name": "Mensuration",
        "children": [
            {"code": "0580.5.1", "name": "Perimeter and area", "keywords": [
                "perimeter", "area", "rectangle", "triangle", "parallelogram", "trapezium",
                "circle", "sector", "arc", "segment", "shaded region", "compound shape"]},
            {"code": "0580.5.2", "name": "Surface area and volume", "keywords": [
                "volume", "surface area", "cuboid", "prism", "cylinder", "cone", "sphere",
                "pyramid", "capacity", "litre", "net", "cross-section"]},
        ],
    },
    {
        "code": "0580.6",
        "name": "Trigonometry",
        "children": [
            {"code": "0580.6.1", "name": "Right-angled triangles", "keywords": [
                "pythagoras", "hypotenuse", "sin", "cos", "tan", "sine", "cosine",
                "tangent", "right-angled", "angle of elevation", "angle of depression"]},
            {"code": "0580.6.2", "name": "Sine and cosine rules", "keywords": [
                "sine rule", "cosine rule", "area of triangle", "obtuse", "ambiguous"]},
            {"code": "0580.6.3", "name": "Trigonometric graphs and identities", "keywords": [
                "trigonometric graph", "amplitude", "period", "identity", "sin2", "cos2"]},
            {"code": "0580.6.4", "name": "Bearings and three dimensions", "keywords": [
                "bearing", "north", "three-dimensional", "3d", "angle between", "plane"]},
        ],
    },
    {
        "code": "0580.7",
        "name": "Vectors and transformations",
        "children": [
            {"code": "0580.7.1", "name": "Vectors", "keywords": [
                "vector", "column vector", "magnitude", "direction", "position vector",
                "scalar multiple", "parallel vectors"]},
        ],
    },
    {
        "code": "0580.8",
        "name": "Probability",
        "children": [
            {"code": "0580.8.1", "name": "Probability", "keywords": [
                "probability", "chance", "likely", "outcome", "sample space",
                "mutually exclusive", "independent", "tree diagram", "conditional",
                "without replacement", "at least", "expected number"]},
        ],
    },
    {
        "code": "0580.9",
        "name": "Statistics",
        "children": [
            {"code": "0580.9.1", "name": "Data and charts", "keywords": [
                "bar chart", "pie chart", "histogram", "frequency", "pictogram",
                "stem and leaf", "table", "tally", "data"]},
            {"code": "0580.9.2", "name": "Averages and spread", "keywords": [
                "mean", "median", "mode", "range", "interquartile", "quartile",
                "average", "cumulative frequency", "box-and-whisker", "standard deviation"]},
            {"code": "0580.9.3", "name": "Scatter diagrams and correlation", "keywords": [
                "scatter", "correlation", "line of best fit", "positive correlation",
                "negative correlation", "outlier", "trend"]},
        ],
    },
]


# --------------------------------------------------------------------------
# 9709 Mathematics (AS and A Level)
# --------------------------------------------------------------------------

_9709: list[SeedNode] = [
    {
        "code": "9709.P1",
        "name": "Pure Mathematics 1",
        "children": [
            {"code": "9709.P1.1", "name": "Quadratics", "keywords": [
                "quadratic", "discriminant", "completing the square", "roots", "coefficient"]},
            {"code": "9709.P1.2", "name": "Functions", "keywords": [
                "function", "domain", "range", "inverse", "composite", "one-one", "graph of"]},
            {"code": "9709.P1.3", "name": "Coordinate geometry", "keywords": [
                "circle", "centre", "radius", "tangent", "normal", "gradient", "midpoint",
                "perpendicular", "equation of the line"]},
            {"code": "9709.P1.4", "name": "Circular measure", "keywords": [
                "radian", "arc", "sector", "segment", "circular measure", "perimeter of the shape"]},
            {"code": "9709.P1.5", "name": "Trigonometry", "keywords": [
                "sin", "cos", "tan", "identity", "prove the identity", "solve the equation",
                "trigonometric", "cosec", "sec", "cot", "exact value"]},
            {"code": "9709.P1.6", "name": "Series", "keywords": [
                "binomial", "expansion", "arithmetic progression", "geometric progression",
                "sum to infinity", "nth term", "series", "convergent"]},
            {"code": "9709.P1.7", "name": "Differentiation", "keywords": [
                "differentiate", "derivative", "gradient of the curve", "stationary",
                "increasing", "decreasing", "tangent", "normal", "rate of change",
                "chain rule", "product rule", "quotient rule", "second derivative"]},
            {"code": "9709.P1.8", "name": "Integration", "keywords": [
                "integrate", "integral", "area under", "volume of revolution",
                "definite integral", "trapezium rule", "reverse"]},
        ],
    },
    {
        "code": "9709.P3",
        "name": "Pure Mathematics 2 and 3",
        "children": [
            {"code": "9709.P3.1", "name": "Algebra", "keywords": [
                "modulus", "partial fraction", "polynomial", "remainder", "factor theorem",
                "quotient", "logarithm", "ln", "exponential", "index law"]},
            {"code": "9709.P3.2", "name": "Logarithmic and exponential functions", "keywords": [
                "log", "ln", "exponential", "growth", "decay", "natural logarithm"]},
            {"code": "9709.P3.3", "name": "Trigonometry (advanced)", "keywords": [
                "tan", "sec", "cosec", "cot", "compound angle", "double angle",
                "harmonic", "radian", "sketch the graph"]},
            {"code": "9709.P3.4", "name": "Differentiation (advanced)", "keywords": [
                "implicit", "parametric", "quotient", "product", "connected rates",
                "second derivative", "stationary point"]},
            {"code": "9709.P3.5", "name": "Integration (advanced)", "keywords": [
                "integration by parts", "substitution", "partial fraction", "volume of revolution",
                "improper integral", "exact value"]},
            {"code": "9709.P3.6", "name": "Numerical solution of equations", "keywords": [
                "iterative", "iteration", "converge", "sign change", "between", "decimal places"]},
            {"code": "9709.P3.7", "name": "Vectors", "keywords": [
                "vector", "scalar product", "perpendicular", "skew", "intersect",
                "line", "plane", "position vector", "direction"]},
            {"code": "9709.P3.8", "name": "Differential equations", "keywords": [
                "differential equation", "separate the variables", "general solution",
                "particular solution", "rate of"]},
            {"code": "9709.P3.9", "name": "Complex numbers", "keywords": [
                "complex", "imaginary", "argand", "modulus", "argument", "locus",
                "real part", "conjugate"]},
        ],
    },
    {
        "code": "9709.M",
        "name": "Mechanics",
        "children": [
            {"code": "9709.M.1", "name": "Forces and equilibrium", "keywords": [
                "force", "equilibrium", "resultant", "friction", "tension", "normal reaction",
                "weight", "inclined plane", "limiting", "coefficient of friction", "moment"]},
            {"code": "9709.M.2", "name": "Kinematics", "keywords": [
                "velocity", "acceleration", "displacement", "distance travelled",
                "constant acceleration", "speed-time", "projectile"]},
            {"code": "9709.M.3", "name": "Momentum and impulse", "keywords": [
                "momentum", "impulse", "collision", "restitution", "coalesce", "conservation"]},
            {"code": "9709.M.4", "name": "Newton's laws of motion", "keywords": [
                "newton", "mass", "acceleration", "connected particles", "pulley", "tow"]},
            {"code": "9709.M.5", "name": "Energy, work and power", "keywords": [
                "work", "energy", "kinetic", "potential", "power", "efficiency",
                "conservation of energy"]},
        ],
    },
    {
        "code": "9709.S",
        "name": "Probability and Statistics",
        "children": [
            {"code": "9709.S.1", "name": "Representation of data", "keywords": [
                "histogram", "frequency density", "box-and-whisker", "cumulative frequency",
                "quartile", "percentile", "outlier", "stem and leaf", "mean", "median",
                "mode", "standard deviation", "variance", "coded"]},
            {"code": "9709.S.2", "name": "Permutations and combinations", "keywords": [
                "permutation", "combination", "arrangement", "selection", "factorial",
                "in how many ways"]},
            {"code": "9709.S.3", "name": "Probability", "keywords": [
                "probability", "mutually exclusive", "independent", "conditional",
                "tree diagram", "venn diagram", "given that"]},
            {"code": "9709.S.4", "name": "Discrete random variables", "keywords": [
                "random variable", "probability distribution", "expectation", "e(x)",
                "variance", "binomial", "geometric", "distribution"]},
            {"code": "9709.S.5", "name": "Normal distribution", "keywords": [
                "normal distribution", "standard normal", "z-value", "continuity correction",
                "approximation", "mean and variance"]},
        ],
    },
]


# --------------------------------------------------------------------------
# 0620 Chemistry (IGCSE)
# --------------------------------------------------------------------------

_0620: list[SeedNode] = [
    {"code": "0620.1", "name": "States of matter", "keywords": [
        "solid", "liquid", "gas", "melting", "boiling", "evaporation", "condensation",
        "sublimation", "particle", "kinetic", "diffusion", "state change", "heating curve"]},
    {"code": "0620.2", "name": "Atoms, elements and compounds", "keywords": [
        "atom", "element", "compound", "mixture", "molecule", "ion", "proton", "neutron",
        "electron", "isotope", "atomic number", "mass number", "periodic table",
        "ionic bond", "covalent bond", "metallic", "giant structure", "formula"]},
    {"code": "0620.3", "name": "Stoichiometry", "keywords": [
        "mole", "relative atomic mass", "relative molecular mass", "empirical formula",
        "molecular formula", "percentage yield", "limiting reactant", "concentration",
        "titration", "avogadro", "stoichiometry"]},
    {"code": "0620.4", "name": "Electrochemistry", "keywords": [
        "electrolysis", "electrolyte", "anode", "cathode", "electrode", "cathode",
        "anion", "cation", "electroplating", "fuel cell", "hydrogen oxygen"]},
    {"code": "0620.5", "name": "Chemical energetics", "keywords": [
        "exothermic", "endothermic", "enthalpy", "energy change", "bond energy",
        "activation energy", "energy level diagram", "combustion"]},
    {"code": "0620.6", "name": "Chemical reactions", "keywords": [
        "rate of reaction", "catalyst", "collision", "surface area", "temperature",
        "concentration", "reversible", "equilibrium", "redox", "oxidation", "reduction",
        "oxidising agent", "reducing agent"]},
    {"code": "0620.7", "name": "Acids, bases and salts", "keywords": [
        "acid", "base", "alkali", "salt", "neutralisation", "ph", "indicator",
        "oxide", "preparation of salts", "soluble", "insoluble", "test for"]},
    {"code": "0620.8", "name": "The periodic table", "keywords": [
        "periodic table", "group", "period", "alkali metal", "halogen", "noble gas",
        "transition element", "reactivity", "trend"]},
    {"code": "0620.9", "name": "Metals", "keywords": [
        "metal", "alloy", "extraction", "blast furnace", "reactivity series",
        "corrosion", "rusting", "sacrificial", "steel", "aluminium", "iron", "copper"]},
    {"code": "0620.10", "name": "Chemistry of the environment", "keywords": [
        "air", "pollution", "greenhouse", "global warming", "ozone", "acid rain",
        "water treatment", "photosynthesis", "carbon cycle", "climate"]},
    {"code": "0620.11", "name": "Organic chemistry", "keywords": [
        "organic", "hydrocarbon", "alkane", "alkene", "alcohol", "carboxylic acid",
        "polymer", "ester", "isomer", "fractional distillation", "cracking",
        "addition", "substitution", "fermentation", "homologous"]},
    {"code": "0620.12", "name": "Experimental techniques and analysis", "keywords": [
        "apparatus", "chromatography", "distillation", "filtration", "crystallisation",
        "purity", "melting point", "flame test", "gas test", "anion", "cation",
        "separation", "locating agent"]},
]


# --------------------------------------------------------------------------
# 0478 Computer Science (IGCSE)
# --------------------------------------------------------------------------

_0478: list[SeedNode] = [
    {"code": "0478.1", "name": "Computer systems", "keywords": [], "children": [
        {"code": "0478.1.1", "name": "Data representation", "keywords": [
            "binary", "denary", "hexadecimal", "bit", "byte", "nibble", "ascii",
            "unicode", "two's complement", "overflow", "sound", "image", "sampling",
            "resolution", "compression", "file size"]},
        {"code": "0478.1.2", "name": "Data transmission", "keywords": [
            "transmission", "simplex", "duplex", "serial", "parallel", "packet",
            "usb", "ethernet", "ip address", "mac address", "protocol", "encryption",
            "bandwidth", "latency", "wireless"]},
        {"code": "0478.1.3", "name": "Hardware", "keywords": [
            "cpu", "processor", "ram", "rom", "cache", "register", "clock",
            "input device", "output device", "sensor", "storage", "ssd", "hdd",
            "optical", "embedded", "fetch-execute", "von neumann"]},
        {"code": "0478.1.4", "name": "Software", "keywords": [
            "operating system", "interrupt", "compiler", "interpreter", "assembler",
            "high-level", "low-level", "ide", "translator", "system software",
            "application software", "utility"]},
        {"code": "0478.1.5", "name": "Internet and its uses", "keywords": [
            "internet", "world wide web", "url", "http", "browser", "search engine",
            "blog", "wiki", "digital currency", "cloud", "hosting"]},
        {"code": "0478.1.6", "name": "Automated and emerging technologies", "keywords": [
            "automated", "robotics", "artificial intelligence", "expert system",
            "machine learning", "augmented reality", "dna", "quantum"]},
        {"code": "0478.1.7", "name": "Security", "keywords": [
            "security", "malware", "virus", "phishing", "pharming", "firewall",
            "proxy", "authentication", "biometric", "two-step", "captcha",
            "brute force", "ddos", "spyware", "ransomware"]},
        {"code": "0478.1.8", "name": "Ethics", "keywords": [
            "ethic", "legal", "copyright", "privacy", "plagiarism", "digital divide",
            "surveillance", "net neutrality"]},
    ]},
    {"code": "0478.2", "name": "Algorithms, programming and logic", "keywords": [], "children": [
        {"code": "0478.2.1", "name": "Algorithm design and problem solving", "keywords": [
            "algorithm", "pseudocode", "flowchart", "decomposition", "abstraction",
            "validation", "verification", "test data", "trace table", "dry run",
            "structure diagram", "stepwise refinement"]},
        {"code": "0478.2.2", "name": "Programming", "keywords": [
            "variable", "constant", "data type", "assignment", "iteration", "loop",
            "selection", "if", "case", "procedure", "function", "parameter",
            "array", "string", "input", "output", "file handling", "nested loop",
            "totalling", "counting", "maximum", "minimum", "average", "linear search",
            "bubble sort", "subroutine"]},
        {"code": "0478.2.3", "name": "Logic", "keywords": [
            "logic gate", "and gate", "or gate", "not gate", "nand", "nor", "xor",
            "truth table", "boolean", "logic circuit", "logic expression"]},
    ]},
    {"code": "0478.3", "name": "Databases", "keywords": [
        "database", "table", "record", "field", "primary key", "foreign key",
        "query", "sql", "select", "from", "where", "order by", "sort", "report",
        "single-table", "data type", "validation rule"]},
    {"code": "0478.4", "name": "Networks", "keywords": [
        "network", "lan", "wan", "topology", "star", "mesh", "router", "switch",
        "nic", "server", "client", "wi-fi", "bluetooth", "cloud", "packet",
        "network security", "encryption", "firewall"]},
]


SEEDS: dict[str, list[SeedNode]] = {
    "0580": _0580,
    "9709": _9709,
    "0620": _0620,
    "0478": _0478,
}
