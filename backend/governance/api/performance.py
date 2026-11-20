from fastapi import APIRouter, Response

from ..performance import read_report

router = APIRouter()


@router.get("/api/performance")
def get_performance(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "benchmark": read_report("benchmark"),
        "fixtures": read_report("fixtures"),
        "tests": read_report("tests"),
    }
