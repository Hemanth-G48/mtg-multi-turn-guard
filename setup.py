from setuptools import setup, find_namespace_packages


setup(
    name="mtg-multi-turn-guard",
    version="0.1",
    description="MTG (Multi-Turn Guard): a framework for detecting and mitigating multi-turn manipulation attacks against LLMs.",
    long_description=(
        "MTG (Multi-Turn Guard) detects and mitigates multi-turn manipulation "
        "attacks against Large Language Models by combining semantic/pattern risk "
        "scoring with a threshold-based security decision engine."
    ),
    long_description_content_type="text/markdown",
    author="[MY NAME]",
    author_email="[MY EMAIL]",
    url="[MY GITHUB REPOSITORY URL]",
    license="MIT",
    packages=find_namespace_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pyyaml==6.0.2",
        "google-generativeai==0.8.3",
        "openai==1.55.2",
        "anthropic==0.39.0",
        "pandas==2.1.3",
        "python-dotenv==1.0.1",
        "watchdog==6.0.0",
        "pydantic",
    ],
)

# now run pip install -e .
