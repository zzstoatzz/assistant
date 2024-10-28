import controlflow as cf
from prefect import flow

from app.settings import settings
from assistant.utilities.loggers import get_logger

logger = get_logger()


@flow
def check_observations(agents: list[cf.Agent]) -> None:
    """Check observations on disk and process if necessary"""

    # Only get unprocessed summaries
    summary_files = list(settings.summaries_dir.glob('*.json'))
    unprocessed_summaries = [
        p
        for p in summary_files
        if p.parent == settings.summaries_dir  # Exclude files in processed subdir
    ]

    if not unprocessed_summaries:
        return None

    summaries = [p.read_text() for p in unprocessed_summaries]

    maybe_interesting_stuff = cf.run(
        'Check if any of the summaries are interesting, reach out to the human if they are',
        agents=agents,
        context={'summaries': summaries},
    )

    # Move processed files to processed directory
    for file_path in unprocessed_summaries:
        new_path = settings.processed_summaries_dir / file_path.name
        file_path.rename(new_path)
        logger.info(f'Moved processed summary: {file_path.name}')

    return maybe_interesting_stuff
