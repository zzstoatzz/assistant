# /// script
# dependencies = [
#   "python-dotenv",
#   "rich"
# ]
# ///

import os

from dotenv import load_dotenv
from rich import print
from rich.console import Console

console = Console()

CORE_VARS = ['OPENAI_API_KEY', 'PREFECT_API_KEY', 'PREFECT_API_URL']
PROCESSORS = {
    'EMAIL': [
        ('EMAIL_CREDENTIALS_PATH', 'app/secrets/gmail_credentials.json'),
        ('EMAIL_TOKEN_PATH', 'app/secrets/gmail_token.json'),
    ],
    'GITHUB': ['GITHUB_TOKEN'],
    'SLACK': ['SLACK_BOT_TOKEN'],
}


def check_env():
    """Check environment configuration"""
    load_dotenv()

    console.rule('[bold]Core Environment')
    for var in CORE_VARS:
        if os.getenv(var):
            print(f'[green]✓[/green] {var}')
        else:
            print(f'[yellow]![/yellow] Missing {var}')

    console.rule('[bold]Available Processors')
    enabled_count = 0
    for proc, deps in PROCESSORS.items():
        is_enabled = os.getenv(f'{proc}_ENABLED')
        status = '[green]✓[/green]' if is_enabled else '[gray]○[/gray]'
        print(f'{status} {proc} {"(enabled)" if is_enabled else "(disabled)"}')

        if is_enabled:
            enabled_count += 1
            for dep in deps:
                if isinstance(dep, tuple):
                    var, default = dep
                    if os.getenv(var):
                        print(f'  [green]✓[/green] {var}')
                    else:
                        print(f'  [blue]i[/blue] {var} (defaulting to {default})')
                else:
                    if os.getenv(dep):
                        print(f'  [green]✓[/green] {dep}')
                    else:
                        print(f'  [yellow]![/yellow] Missing {dep}')

    if not enabled_count:
        print(
            '\n[yellow]No processors enabled[/yellow]. Enable with:'
            '\n  • GITHUB_ENABLED=true'
            '\n  • EMAIL_ENABLED=true'
            '\n  • SLACK_ENABLED=true'
        )

    print('\n[bold green]→[/bold green] Run [bold]just dev[/bold] for local development')
    print('[bold green]→[/bold green] Run [bold]just -l[/bold] to see all available commands')


if __name__ == '__main__':
    check_env()
