# /// script
# dependencies = [
#     "controlflow",
# ]
# ///

import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

import controlflow as cf
from controlflow.tools import code, filesystem
from pydantic import BaseModel, Field


def python(code: str) -> str:
    with NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(code.encode())
        subprocess.run(["uv", "run", f.name])


def pip_install(
    package_or_packages: Annotated[
        str,
        Field(
            description="A package or a list of packages to install as a string",
            examples=["pandas", "numpy scikit-learn"],
        ),
    ],
) -> None:
    subprocess.run(["uv", "pip", "install", package_or_packages])


class DesignDoc(BaseModel):
    goals: str
    design: str
    implementation_details: str
    criteria: str


# Load the instructions
instructions = (Path.cwd() / "instructions.md").read_text()

# Create the agent
engineer = cf.Agent(
    name="Engineer",
    instructions=instructions,
    tools=[
        *filesystem.ALL_TOOLS,
        code.shell,
        pip_install,
        python,
    ],
)


@cf.flow(
    default_agent=engineer, instructions="Do not give up until the software works."
)
def software_engineer_flow():
    # Task 1: Create design document
    design_doc = cf.run(
        "Learn about the software the user wants to build",
        instructions="""
            Interact with the user to understand the software they want to build.
            What is its purpose? What language should you use? What does it need to do?
            Engage in a natural conversation to collect information.
            Once you have enough, write out a design document to complete the task.
            """,
        interactive=True,
        result_type=DesignDoc,
    )

    # Task 2: Create project directory
    project_dir = cf.run(
        "Create a directory for the software",
        instructions="""
            Create a directory to store the software and related files.
            The directory should be named after the software. Return the path.
            """,
        result_type=str,
        tools=[filesystem.mkdir],
    )

    # Task 3: Implement the software
    cf.run(
        "Implement the software",
        instructions="""
            Implement the software based on the design document.
            All files must be written to the provided project directory.
            Continue building and refining until the software runs as expected and meets all requirements.
            Update the user on your progress regularly.
            """,
        context=dict(design_doc=design_doc, project_dir=project_dir),
        result_type=None,
    )


if __name__ == "__main__":
    software_engineer_flow()
