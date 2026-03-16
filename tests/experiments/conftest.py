def pytest_addoption(parser):
    parser.addoption("--run-llm", action="store_true", default=False, help="Run LLM experiment tests (costs real money)")
