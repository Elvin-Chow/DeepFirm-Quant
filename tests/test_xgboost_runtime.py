from models.xgboost_runtime import import_xgboost


def test_import_xgboost_runtime_loads_classifier() -> None:
    xgb = import_xgboost()

    assert hasattr(xgb, "XGBClassifier")
