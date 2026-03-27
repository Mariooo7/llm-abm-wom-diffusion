from pathlib import Path

import matplotlib as mpl

FIGURES_DIR = Path("analysis/figures")
FIGURE_EXTENSION = ".pdf"


def configure_matplotlib() -> None:
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42
    mpl.rcParams["savefig.bbox"] = "tight"


def figure_path(stem: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    return FIGURES_DIR / f"{stem}{FIGURE_EXTENSION}"
