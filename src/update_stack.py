import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


USERNAME = "michellvagner"
PROFILE_REPO = "michellvagner"

README_FILE = Path("README.md")

START_MARKER = "<!-- STACK_USAGE_START -->"
END_MARKER = "<!-- STACK_USAGE_END -->"


def github_get(url):
    """GET autenticado na API do GitHub."""
    token = os.environ.get("GH_TOKEN")

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def get_repositories():
    """Busca todos os repositórios públicos do usuário."""
    repositories = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?type=owner&per_page=100&page={page}"
        )

        data = github_get(url)

        if not data:
            break

        repositories.extend(data)
        page += 1

    # Remove forks, arquivados e o próprio repositório do perfil
    repositories = [
        repo
        for repo in repositories
        if not repo["fork"]
        and not repo["archived"]
        and repo["name"] != PROFILE_REPO
        and not repo["disabled"]
    ]

    return repositories


def get_tree(repo):
    """Busca todos os arquivos do repositório."""
    owner = repo["owner"]["login"]
    name = repo["name"]
    branch = repo["default_branch"]

    encoded_branch = urllib.parse.quote(branch, safe="")

    url = (
        f"https://api.github.com/repos/{owner}/{name}"
        f"/git/trees/{encoded_branch}?recursive=1"
    )

    try:
        data = github_get(url)
        return [
            item["path"]
            for item in data.get("tree", [])
            if item["type"] == "blob"
        ]

    except Exception as error:
        print(f"Erro ao ler {repo['full_name']}: {error}")
        return []


def normalize(path):
    return path.lower().replace("\\", "/")


def contains_any(paths, values):
    return any(
        any(value in path for value in values)
        for path in paths
    )


def detect_technologies(repo, paths):
    """
    Identifica tecnologias por arquivos, diretórios
    e informações do próprio repositório.
    """

    normalized_paths = [normalize(path) for path in paths]

    repo_name = repo["name"].lower()
    description = (repo.get("description") or "").lower()

    text = " ".join(
        normalized_paths
        + [repo_name, description]
    )

    technologies = set()

    # -------------------------
    # Python
    # -------------------------

    if (
        any(path.endswith(".py") for path in normalized_paths)
        or contains_any(
            normalized_paths,
            [
                "requirements.txt",
                "pyproject.toml",
                "setup.py",
                "poetry.lock",
            ],
        )
    ):
        technologies.add("Python")

    # -------------------------
    # SQL
    # -------------------------

    if any(path.endswith(".sql") for path in normalized_paths):
        technologies.add("SQL")

    # -------------------------
    # Terraform
    # -------------------------

    if (
        any(path.endswith(".tf") for path in normalized_paths)
        or "terraform" in text
    ):
        technologies.add("Terraform")

    # -------------------------
    # Docker
    # -------------------------

    if any(
        path.split("/")[-1] in {
            "dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
        }
        for path in normalized_paths
    ):
        technologies.add("Docker")

    # -------------------------
    # GitHub Actions
    # -------------------------

    if any(
        path.startswith(".github/workflows/")
        and path.endswith((".yml", ".yaml"))
        for path in normalized_paths
    ):
        technologies.add("GitHub Actions")

    # -------------------------
    # AWS
    # -------------------------

    if contains_any(
        normalized_paths,
        [
            "aws",
            "boto3",
            "sam-template",
            "serverless.yml",
            "serverless.yaml",
        ],
    ):
        technologies.add("AWS")

    # Também considera Terraform + AWS
    if any(path.endswith(".tf") for path in normalized_paths):
        if "aws" in text:
            technologies.add("AWS")

    # -------------------------
    # Snowflake
    # -------------------------

    if "snowflake" in text or "snowpark" in text:
        technologies.add("Snowflake")

    # -------------------------
    # dbt
    # -------------------------

    if contains_any(
        normalized_paths,
        [
            "dbt_project.yml",
            "dbt_project.yaml",
            "profiles.yml",
            "profiles.yaml",
        ],
    ):
        technologies.add("dbt")

    if "dbt" in text:
        technologies.add("dbt")

    # -------------------------
    # Apache Airflow
    # -------------------------

    if (
        "airflow" in text
        or any("/dags/" in path for path in normalized_paths)
        or any(
            path.endswith("airflow.cfg")
            for path in normalized_paths
        )
    ):
        technologies.add("Airflow")

    # -------------------------
    # Apache Spark
    # -------------------------

    if (
        "spark" in text
        or any(
            "pyspark" in path
            for path in normalized_paths
        )
    ):
        technologies.add("Spark")

    # -------------------------
    # Power BI
    # -------------------------

    if any(
        path.endswith(".pbix")
        for path in normalized_paths
    ):
        technologies.add("Power BI")

    if "powerbi" in text or "power-bi" in text:
        technologies.add("Power BI")

    # -------------------------
    # Power Automate
    # -------------------------

    if (
        "powerautomate" in text
        or "power-automate" in text
        or "power automate" in description
    ):
        technologies.add("Power Automate")

    return technologies


def make_bar(percentage, width=20):
    filled = round((percentage / 100) * width)
    return "█" * filled + "░" * (width - filled)


def generate_markdown(stats, total_repositories):
    if total_repositories == 0:
        return "Nenhum repositório encontrado."

    lines = []

    lines.append(
        f"**{total_repositories} repositórios analisados**"
    )
    lines.append("")
    lines.append(
        "> Percentual de repositórios que utilizam cada tecnologia."
    )
    lines.append(
        "> Um projeto pode utilizar várias tecnologias."
    )
    lines.append("")

    for technology, count in stats:
        percentage = round(
            (count / total_repositories) * 100
        )

        bar = make_bar(percentage)

        lines.append(
            f"**{technology:<16}** "
            f"`{bar}` **{percentage}%** "
            f"({count}/{total_repositories})"
        )

    return "\n".join(lines)


def update_readme(content):
    readme = README_FILE.read_text(
        encoding="utf-8"
    )

    if START_MARKER not in readme:
        raise RuntimeError(
            f"Não encontrei {START_MARKER} no README.md"
        )

    if END_MARKER not in readme:
        raise RuntimeError(
            f"Não encontrei {END_MARKER} no README.md"
        )

    before = readme.split(
        START_MARKER,
        1
    )[0]

    after = readme.split(
        END_MARKER,
        1
    )[1]

    new_readme = (
        before
        + START_MARKER
        + "\n"
        + content
        + "\n"
        + END_MARKER
        + after
    )

    README_FILE.write_text(
        new_readme,
        encoding="utf-8"
    )


def main():
    print("Buscando repositórios...")

    repositories = get_repositories()

    print(
        f"{len(repositories)} repositórios encontrados."
    )

    technology_counts = {}

    for repo in repositories:
        print(
            f"Analisando {repo['full_name']}..."
        )

        paths = get_tree(repo)

        technologies = detect_technologies(
            repo,
            paths
        )

        for technology in technologies:
            technology_counts[technology] = (
                technology_counts.get(technology, 0) + 1
            )

    stats = sorted(
        technology_counts.items(),
        key=lambda item: item[1],
        reverse=True
    )

    markdown = generate_markdown(
        stats,
        len(repositories)
    )

    update_readme(markdown)

    print("\nREADME atualizado!")
    print("\n" + markdown)


if __name__ == "__main__":
    main()