import pathlib
import pandas as pd
import networkx as nx
from typing import List, Tuple
from io import StringIO
import click

LICENSE_DATA = """License,Use_Freedom,Modify_Freedom,Distribute_Freedom,Attribution_Required,Copyleft_Strength,Network_Copyleft,Patent_Grant,Trademark_Protection,Endorsement_Prohibition,Warranty_Disclaimer,Liability_Limitation,Source_Disclosure_Required,Compatible_With_Proprietary
Proprietary,Limited,No,No,No,Absent,No,No,Yes,Yes,No,No,No,Yes
AGPL-3.0,Yes,Yes,Yes,Yes,Strong,Yes,Yes,No,No,Yes,Yes,Yes,No
GPL-3.0,Yes,Yes,Yes,Yes,Strong,No,Yes,No,No,Yes,Yes,Yes,No
GPL-2.0,Yes,Yes,Yes,Yes,Strong,No,Limited,No,No,Yes,Yes,Yes,No
LGPL-3.0,Yes,Yes,Yes,Yes,Weak,No,Yes,No,No,Yes,Yes,Limited,Limited
LGPL-2.1,Yes,Yes,Yes,Yes,Weak,No,Limited,No,No,Yes,Yes,Limited,Limited
Apache-2.0,Yes,Yes,Yes,Yes,Absent,No,Yes,No,No,Yes,Yes,No,Yes
MIT,Yes,Yes,Yes,Yes,Absent,No,No,No,No,Yes,Yes,No,Yes
BSD-3-Clause,Yes,Yes,Yes,Yes,Absent,No,No,No,Yes,Yes,Yes,No,Yes
BSD-2-Clause,Yes,Yes,Yes,Yes,Absent,No,No,No,No,Yes,Yes,No,Yes
ISC,Yes,Yes,Yes,Yes,Absent,No,No,No,No,Yes,Yes,No,Yes
Unlicense,Yes,Yes,Yes,No,Absent,No,No,No,No,No,No,No,Yes
CC0,Yes,Yes,Yes,No,Absent,No,No,No,No,No,No,No,Yes
BSL-1.1,Limited,Yes,Yes,Yes,Absent,No,Yes,No,No,Yes,Yes,Yes,Limited
"""


def load_license_data() -> pd.DataFrame:
    """Load license data from embedded CSV."""
    df = pd.read_csv(StringIO(LICENSE_DATA))
    return df.loc[~df["License"].apply(lambda x: x.startswith("BSL"))].copy()


def convert_to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convert license properties to numeric values for comparison."""
    conversion_map = {
        "Use_Freedom": {"Yes": 1, "Limited": 0.2, "No": 0},
        "Modify_Freedom": {"Yes": 1, "No": 0},
        "Distribute_Freedom": {"Yes": 1, "No": 0},
        # FIXED: Map restrictions so higher = more restrictive
        "Attribution_Required": {"Yes": 1, "No": 0},
        "Copyleft_Strength": {"Strong": 3, "Weak": 2, "Absent": 0},  # Fixed: Absent=0
        "Network_Copyleft": {"Yes": 1, "No": 0},
        "Patent_Grant": {"Yes": 1, "Limited": 0.5, "No": 0},
        "Trademark_Protection": {"Yes": 1, "No": 0},
        "Endorsement_Prohibition": {"Yes": 1, "No": 0},
        "Warranty_Disclaimer": {"Yes": 1, "No": 0},
        "Liability_Limitation": {"Yes": 1, "No": 0},
        "Source_Disclosure_Required": {"Yes": 1, "Limited": 0.5, "No": 0},
        "Compatible_With_Proprietary": {"Yes": 0, "Limited": 0.5, "No": 1},
    }

    df_numeric = df.copy()
    for col, mapping in conversion_map.items():
        df_numeric[col] = df_numeric[col].map(mapping)

    return df_numeric


def calculate_openness_score(row: pd.Series) -> float:
    """Calculate overall openness score for a license. Higher scores = more open.
    Fixed: Proper mapping now aligns with weights where:
    - Negative weights reduce openness (restrictions)
    - Positive weights increase openness (freedoms)"""
    weights = {
        "Use_Freedom": 4.0,
        "Modify_Freedom": 4.0,
        "Distribute_Freedom": 4.0,
        "Patent_Grant": 0.5,
        "Compatible_With_Proprietary": 0.0,
        "Attribution_Required": -1.0,
        "Copyleft_Strength": -2.0,
        "Network_Copyleft": -2.0,
        "Trademark_Protection": -1.0,
        "Endorsement_Prohibition": -0.5,
        "Warranty_Disclaimer": -0.2,
        "Liability_Limitation": -0.2,
        "Source_Disclosure_Required": -2.0,
    }

    openness_score = 0
    for prop, weight in weights.items():
        openness_score += row[prop] * weight

    return openness_score


def is_less_open_than(license1: pd.Series, license2: pd.Series) -> bool:
    """Check if license1 is less open (more restrictive) than license2."""
    # Freedom aspects: license1 should have <= freedom compared to license2
    freedom_aspects = [
        "Use_Freedom",
        "Modify_Freedom",
        "Distribute_Freedom",
        "Patent_Grant",
        "Compatible_With_Proprietary",  # Added as freedom aspect
    ]

    # Requirement/Restriction aspects: license1 should have >= restrictions
    requirement_aspects = [
        "Attribution_Required",
        "Copyleft_Strength",
        "Network_Copyleft",
        "Trademark_Protection",
        "Endorsement_Prohibition",
        "Warranty_Disclaimer",
        "Liability_Limitation",
        "Source_Disclosure_Required",
    ]

    # Check license1 is not more open in any aspect
    for aspect in freedom_aspects:
        if license1[aspect] > license2[aspect]:
            return False
    for aspect in requirement_aspects:
        if license1[aspect] < license2[aspect]:
            return False

    # Check at least one aspect is strictly less open
    for aspect in freedom_aspects:
        if license1[aspect] < license2[aspect]:
            return True
    for aspect in requirement_aspects:
        if license1[aspect] > license2[aspect]:
            return True

    return False


def find_direct_relationships(df: pd.DataFrame) -> List[Tuple[str, str]]:
    """Find direct 'less open than' relationships between licenses."""
    relationships = []
    licenses = df["License"].tolist()

    for i, license1 in enumerate(licenses):
        for j, license2 in enumerate(licenses):
            if i != j:
                if is_less_open_than(df.iloc[i], df.iloc[j]):
                    # Check if this is a direct relationship (not transitive)
                    # A -> C is direct if there's no B such that A -> B -> C
                    is_direct = True
                    for k, intermediate in enumerate(licenses):
                        if k != i and k != j:
                            if is_less_open_than(df.iloc[i], df.iloc[k]) and is_less_open_than(df.iloc[k], df.iloc[j]):
                                is_direct = False
                                break

                    if is_direct:
                        relationships.append((license1, license2))  # Arrow from less open to more open

    return relationships


def create_license_lattice(
        df: pd.DataFrame, relationships: List[Tuple[str, str]]
) -> nx.DiGraph:
    """Create a NetworkX directed graph of the license lattice."""
    G = nx.DiGraph()

    # Color scheme for different license types
    colors = {
        "Proprietary": "#ff6b6b",
        "AGPL-3.0": "#a29bfe",
        "GPL-3.0": "#74b9ff",
        "GPL-2.0": "#74b9ff",
        "LGPL-3.0": "#ffeaa7",
        "LGPL-2.1": "#ffeaa7",
        "Apache-2.0": "#ffecd2",
        "MIT": "#4ecdc4",
        "BSD-3-Clause": "#a8edea",
        "BSD-2-Clause": "#a8edea",
        "ISC": "#a8edea",
        "Unlicense": "#fd79a8",
        "CC0": "#fd79a8",
        "BSL-1.1": "#c8d6e5",
    }

    # Add nodes with attributes
    for _, row in df.iterrows():
        license_name = row["License"]
        color = colors.get(license_name, "#ddd")
        openness = row["Openness_Score"]  # Use the calculated score directly

        G.add_node(
            license_name,
            color=color,
            openness=openness,
            label=f"{license_name}\n(O: {openness:.1f})",
            # Assign a rank attribute for vertical positioning
            rank=str(round(openness))  # Round to nearest integer for discrete ranks
        )

    # Add edges
    for source, target in relationships:
        G.add_edge(source, target)

    return G


def plot_with_pygraphviz(G: nx.DiGraph, fig_path):
    """Plot the license lattice using pygraphviz."""

    # Create pygraphviz graph
    A = nx.nx_agraph.to_agraph(G)

    # Set graph attributes
    A.graph_attr["rankdir"] = "BT"  # Bottom to Top: Less open at bottom, more open at top
    # A.graph_attr['splines'] = 'ortho' # Can uncomment if desired
    A.graph_attr["nodesep"] = "0.7"  # Adjusted for better spacing with ranks
    A.graph_attr["ranksep"] = "1.5"  # Keep ranks separated

    # Set node attributes
    for node_name in A.nodes():
        node = A.get_node(node_name)
        node.attr["shape"] = "box"
        node.attr["style"] = "filled,rounded"
        node.attr["fontname"] = "Arial"
        node.attr["fontsize"] = "10"
        node.attr["fillcolor"] = G.nodes[node_name]["color"]
        node.attr["label"] = G.nodes[node_name]["label"]
        node.attr["rank"] = G.nodes[node_name]["rank"]  # Apply the calculated rank

    # Set edge attributes
    for edge in A.edges():
        edge.attr["arrowhead"] = "normal"
        edge.attr["arrowsize"] = "0.8"

    # Ensure output directory exists
    fig_path.mkdir(parents=True, exist_ok=True)

    # Render the graph
    A.layout(prog="dot")
    A.draw(fig_path / "license_lattice_pygraphviz.png")
    A.draw(fig_path / "license_lattice_pygraphviz.svg")

@click.command()
@click.option(
    "-o", "--figure-output-path", type=click.Path(), default=pathlib.Path("./figs")
)
def main(figure_output_path):
    """Main function to generate the license lattice."""
    print("Loading license data...")
    df = load_license_data()

    print("Converting to numeric values...")
    df_numeric = convert_to_numeric(df)

    print("Calculating openness scores...")
    df_numeric["Openness_Score"] = df_numeric.apply(
        calculate_openness_score, axis=1
    )

    print("\nLicense Openness Ranking (Higher score = More Open):")
    sorted_licenses = df_numeric.sort_values("Openness_Score", ascending=False)
    print(sorted_licenses[['License', 'Openness_Score']].to_string(index=False))

    print("\nFinding direct relationships...")
    relationships = find_direct_relationships(df_numeric)

    print(f"Found {len(relationships)} direct relationships:")
    for source, target in relationships:
        print(f"  {source} -> {target}")

    G = create_license_lattice(df_numeric, relationships)

    plot_with_pygraphviz(G, figure_output_path)



if __name__ == "__main__":
    main()