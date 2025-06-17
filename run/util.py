import pathlib


def crawl_directories(
    input_path: pathlib.Path, suffixes=(".pdf", ".json"), prefix=None
) -> list[pathlib.Path]:
    file_paths: list[pathlib.Path] = []

    if not input_path.is_dir():
        print(f"The path {input_path} is not a valid directory.")
        return file_paths

    for file in input_path.rglob("*"):
        if (
            file.is_file()
            and file.suffix in suffixes
            and (file.stem.startswith(prefix) if prefix is not None else True)
        ):
            file_paths.append(file)
    return file_paths
