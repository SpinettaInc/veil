"""Veil CLI - Privacy-preserving proxy for LLMs."""

import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from veil.core.pipeline import VeilPipeline
from veil.weighting.config import DetectionProfile, WeightConfig, load_profile

# Create Typer app
app = typer.Typer(
    name="veil",
    help="Privacy-preserving proxy for LLMs - anonymize sensitive data before sending to AI",
    add_completion=False,
)

# Rich console for pretty output
console = Console()

# Global pipeline instance for interactive sessions
_pipeline: VeilPipeline | None = None


def get_pipeline(
    use_ner: bool = True,
    use_patterns: bool = True,
    profile: DetectionProfile = DetectionProfile.BALANCED,
    weight_config: "WeightConfig | None" = None,
) -> VeilPipeline:
    """Get or create the global pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = VeilPipeline(
            use_ner=use_ner,
            use_patterns=use_patterns,
            profile=profile,
            weight_config=weight_config,
        )
    return _pipeline


def parse_profile(profile_str: str) -> DetectionProfile:
    """Parse profile string to enum."""
    try:
        return DetectionProfile(profile_str.lower())
    except ValueError:
        valid = ", ".join([p.value for p in DetectionProfile])
        raise typer.BadParameter(f"Invalid profile. Choose from: {valid}")


def parse_profile_or_path(profile_str: str) -> "tuple[DetectionProfile, WeightConfig | None]":
    """Accept a built-in profile name or a path to a profile YAML file."""
    try:
        return parse_profile(profile_str), None
    except typer.BadParameter:
        if Path(profile_str).exists():
            return DetectionProfile.BALANCED, load_profile(profile_str)
        raise


@app.command()
def anonymize(
    text: str | None = typer.Argument(
        None,
        help="Text to anonymize (or use --input for file)",
    ),
    input_file: Path | None = typer.Option(
        None,
        "--input",
        "-i",
        help="Input file to anonymize",
    ),
    output_file: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for anonymized text",
    ),
    show_mapping: bool = typer.Option(
        False,
        "--mapping",
        "-m",
        help="Show the mapping table",
    ),
    no_ner: bool = typer.Option(
        False,
        "--no-ner",
        help="Disable NER detection (patterns only)",
    ),
    no_patterns: bool = typer.Option(
        False,
        "--no-patterns",
        help="Disable pattern detection (NER only)",
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help="Detection profile: paranoid, balanced, minimal",
    ),
    no_weighting: bool = typer.Option(
        False,
        "--no-weighting",
        help="Disable semantic weighting (detect all entities)",
    ),
    replacement_mode: str = typer.Option(
        "token",
        "--mode",
        "-r",
        help="Replacement mode: token, faker, semantic",
    ),
    faker_seed: int | None = typer.Option(
        None,
        "--seed",
        help="Random seed for faker mode (for reproducibility)",
    ),
    hybrid: bool = typer.Option(
        False,
        "--hybrid",
        "-H",
        help="Use hybrid detection (combines spaCy, Presidio, and patterns)",
    ),
    presidio: bool = typer.Option(
        False,
        "--presidio",
        help="Enable Presidio detection (implies --hybrid)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
) -> None:
    """Anonymize sensitive entities in text.

    Examples:
        veil anonymize "John Smith works at Acme Corp"
        veil anonymize --input document.txt --output anonymized.txt
        veil anonymize "My SSN is 123-45-6789" --mapping
        veil anonymize "text" --profile paranoid
        veil anonymize "text" --mode faker
        veil anonymize "text" --mode faker --seed 42
        veil anonymize "text" --hybrid  # Use all detection sources
        veil anonymize "text" --presidio  # Enable Presidio detection
    """
    # Get input text
    if text:
        input_text = text
    elif input_file:
        if not input_file.exists():
            console.print(f"[red]Error:[/red] File not found: {input_file}")
            raise typer.Exit(1)
        input_text = input_file.read_text()
    else:
        # Read from stdin
        if sys.stdin.isatty():
            console.print("[yellow]Enter text to anonymize (Ctrl+D to finish):[/yellow]")
        input_text = sys.stdin.read()

    if not input_text.strip():
        console.print("[yellow]No input text provided[/yellow]")
        raise typer.Exit(0)

    # Parse profile
    detection_profile, weight_config = parse_profile_or_path(profile)

    # Validate replacement mode
    valid_modes = ["token", "faker", "semantic"]
    if replacement_mode.lower() not in valid_modes:
        console.print(f"[red]Error:[/red] Invalid mode. Choose from: {', '.join(valid_modes)}")
        raise typer.Exit(1)

    # Determine detection mode
    use_presidio = presidio
    detection_mode = "hybrid" if (hybrid or presidio) else "standard"

    # Create pipeline
    try:
        pipeline = VeilPipeline(
            use_ner=not no_ner,
            use_patterns=not no_patterns,
            use_presidio=use_presidio,
            profile=detection_profile,
            weight_config=weight_config,
            use_weighting=not no_weighting,
            replacement_mode=replacement_mode.lower(),
            faker_seed=faker_seed,
            detection_mode=detection_mode,
        )
    except ImportError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[dim]Install optional dependencies with: pip install veil[presidio][/dim]")
        raise typer.Exit(1)

    # Anonymize
    result = pipeline.anonymize(input_text)

    # Output
    if json_output:
        import json

        output = {
            "original": result.original_text,
            "anonymized": result.anonymized_text,
            "entities": [e.to_dict() for e in result.entities],
            "mappings": result.replacements,
            "profile": detection_profile.value,
            "replacement_mode": replacement_mode.lower(),
            "detection_mode": detection_mode,
        }
        if output_file:
            output_file.write_text(json.dumps(output, indent=2))
            console.print(f"[green]Output written to {output_file}[/green]")
        else:
            console.print(json.dumps(output, indent=2))
    else:
        if output_file:
            output_file.write_text(result.anonymized_text)
            console.print(f"[green]Output written to {output_file}[/green]")
        else:
            console.print(Panel(result.anonymized_text, title="Anonymized Text"))

        if show_mapping and result.entities:
            _show_mapping_table(result.replacements, result.entities)

        if result.entity_count > 0:
            console.print(
                f"\n[dim]Detected {result.entity_count} entities (profile: {detection_profile.value}, mode: {replacement_mode.lower()})[/dim]"  # noqa: E501
            )


@app.command()
def detect(
    text: str = typer.Argument(..., help="Text to analyze"),
    no_ner: bool = typer.Option(
        False,
        "--no-ner",
        help="Disable NER detection",
    ),
    no_patterns: bool = typer.Option(
        False,
        "--no-patterns",
        help="Disable pattern detection",
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help="Detection profile: paranoid, balanced, minimal",
    ),
    hybrid: bool = typer.Option(
        False,
        "--hybrid",
        "-H",
        help="Use hybrid detection (combines spaCy, Presidio, and patterns)",
    ),
    presidio: bool = typer.Option(
        False,
        "--presidio",
        help="Enable Presidio detection (implies --hybrid)",
    ),
) -> None:
    """Detect and display sensitive entities without anonymizing.

    Shows what would be detected without modifying the text.

    Example:
        veil detect "John Smith, SSN 123-45-6789, works at Acme Corp"
        veil detect "text" --hybrid  # Use all detection sources
    """
    detection_profile, weight_config = parse_profile_or_path(profile)
    detection_mode = "hybrid" if (hybrid or presidio) else "standard"

    pipeline = VeilPipeline(
        use_ner=not no_ner,
        use_patterns=not no_patterns,
        use_presidio=presidio,
        profile=detection_profile,
        weight_config=weight_config,
        use_weighting=False,  # Show all detected, not filtered
        detection_mode=detection_mode,
    )

    entities = pipeline.detector.detect(text)

    if not entities:
        console.print("[yellow]No entities detected[/yellow]")
        return

    # Create table
    table = Table(title="Detected Entities")
    table.add_column("Text", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Position", style="dim")
    table.add_column("Confidence", style="yellow")
    table.add_column("Source", style="dim")

    for entity in entities:
        table.add_row(
            entity.text,
            entity.entity_type.value,
            f"{entity.start}:{entity.end}",
            f"{entity.confidence:.2f}",
            entity.source,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(entities)} entities[/dim]")


@app.command()
def score(
    text: str = typer.Argument(..., help="Text to analyze"),
    no_ner: bool = typer.Option(
        False,
        "--no-ner",
        help="Disable NER detection",
    ),
    no_patterns: bool = typer.Option(
        False,
        "--no-patterns",
        help="Disable pattern detection",
    ),
    profile: str = typer.Option(
        "balanced",
        "--profile",
        "-p",
        help="Detection profile: paranoid, balanced, minimal",
    ),
) -> None:
    """Show privacy scores for detected entities.

    Displays detailed scoring breakdown including base score,
    context boost, rarity, and whether each entity would be anonymized.

    Example:
        veil score "Patient John Smith, SSN 123-45-6789"
    """
    detection_profile, weight_config = parse_profile_or_path(profile)

    pipeline = VeilPipeline(
        use_ner=not no_ner,
        use_patterns=not no_patterns,
        profile=detection_profile,
        weight_config=weight_config,
    )

    scores = pipeline.score_entities(text)

    if not scores:
        console.print("[yellow]No entities detected[/yellow]")
        return

    # Get threshold from scorer
    threshold = pipeline.scorer.config.threshold if pipeline.scorer else 0.5

    # Create table
    table = Table(title=f"Privacy Scores (threshold: {threshold})")
    table.add_column("Entity", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Base", style="yellow")
    table.add_column("Context", style="blue")
    table.add_column("Rarity", style="magenta")
    table.add_column("Total", style="bold")
    table.add_column("Anonymize?", style="green")

    for s in scores:
        anonymize_str = "[green]Yes[/green]" if s.above_threshold else "[red]No[/red]"
        table.add_row(
            s.entity.text[:20] + "..." if len(s.entity.text) > 20 else s.entity.text,
            s.entity.entity_type.value,
            f"{s.base_score:.2f}",
            f"+{s.context_boost:.2f}",
            f"+{s.rarity_boost:.3f}",
            f"{s.total_score:.3f}",
            anonymize_str,
        )

    console.print(table)

    # Summary
    above = sum(1 for s in scores if s.above_threshold)
    console.print(f"\n[dim]{above}/{len(scores)} entities above threshold[/dim]")


@app.command()
def reconstruct(
    text: str = typer.Argument(..., help="Anonymized text to reconstruct"),
    mapping_file: Path | None = typer.Option(
        None,
        "--mapping",
        "-m",
        help="JSON file with mappings",
    ),
) -> None:
    """Reconstruct anonymized text back to original.

    Requires the mapping store from the original anonymization.

    Example:
        veil reconstruct "[PERSON_1] works at [ORG_1]" --mapping mappings.json
    """
    import json

    if mapping_file:
        if not mapping_file.exists():
            console.print(f"[red]Error:[/red] Mapping file not found: {mapping_file}")
            raise typer.Exit(1)

        data = json.loads(mapping_file.read_text())
        from veil.core.mapper import MappingStore

        mapping_store = MappingStore.from_dict(data)
    else:
        # Use global pipeline if available
        pipeline = get_pipeline()
        mapping_store = pipeline.mapping_store

    if len(mapping_store) == 0:
        console.print("[yellow]Warning: No mappings available[/yellow]")
        console.print(text)
        return

    # Reconstruct
    result = text
    replacements = 0
    for entry in mapping_store:
        if entry.replacement in result:
            result = result.replace(entry.replacement, entry.original)
            replacements += 1

    console.print(Panel(result, title="Reconstructed Text"))
    console.print(f"\n[dim]Made {replacements} replacements[/dim]")


@app.command()
def stats() -> None:
    """Show statistics about the current pipeline."""
    pipeline = get_pipeline()
    stats = pipeline.get_stats()

    console.print(Panel.fit("[bold]Veil Pipeline Statistics[/bold]"))

    # Detector stats
    det = stats["detector"]
    console.print("\n[bold]Detector:[/bold]")
    console.print(f"  Mode: {det.get('mode', 'standard')}")
    console.print(f"  NER enabled: {det.get('spacy_enabled', det.get('ner_enabled', False))}")
    if det.get("ner_model") or det.get("spacy_model"):
        console.print(f"  NER model: {det.get('ner_model') or det.get('spacy_model')}")
    console.print(f"  Presidio enabled: {det.get('presidio_enabled', False)}")
    console.print(f"  Patterns enabled: {det.get('patterns_enabled', False)}")
    console.print(f"  Pattern count: {det.get('pattern_count', 0)}")
    if det.get("agreement_boost"):
        console.print(f"  Agreement boost: {det['agreement_boost']}")

    # Profile
    console.print(f"\n[bold]Profile:[/bold] {stats.get('profile', 'balanced')}")
    console.print(f"  Weighting enabled: {stats.get('weighting_enabled', True)}")

    if "scorer" in stats:
        scorer = stats["scorer"]
        console.print(f"  Threshold: {scorer['threshold']}")
        console.print(f"  Rarity factor: {scorer['rarity_factor']}")

    # Replacement mode
    if "replacement" in stats:
        repl = stats["replacement"]
        console.print("\n[bold]Replacement:[/bold]")
        console.print(f"  Mode: {repl.get('mode', 'token')}")
        if repl.get("bracket_style"):
            console.print(f"  Bracket style: {repl['bracket_style']}")
        if repl.get("locale"):
            console.print(f"  Faker locale: {repl['locale']}")

    # Mapping stats
    maps = stats["mappings"]
    console.print("\n[bold]Mappings:[/bold]")
    console.print(f"  Total mappings: {maps['total_mappings']}")
    if maps.get("by_type"):
        console.print("  By type:")
        for entity_type, count in maps["by_type"].items():
            console.print(f"    {entity_type}: {count}")


@app.command()
def version() -> None:
    """Show Veil version information."""
    from veil import __version__

    console.print(f"[bold]Veil[/bold] version {__version__}")
    console.print("Privacy-preserving proxy for LLMs")
    console.print("\n[dim]Profiles: paranoid, balanced, minimal[/dim]")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address (use 0.0.0.0 to expose)"),
    port: int = typer.Option(8787, help="TCP port"),
    profile: str = typer.Option("balanced", "--profile", "-p", help="Profile name or YAML path"),
    detection_mode: str = typer.Option("standard", help="standard or hybrid"),
    session_ttl: float = typer.Option(
        3600.0, help="Seconds of inactivity before a session expires"
    ),
    audit: Path | None = typer.Option(None, "--audit", help="Append JSONL audit log here"),
) -> None:
    """Run the HTTP API server (POST /anonymize, POST /reconstruct, GET /health)."""
    from veil.audit import AuditLogger
    from veil.server import VeilService, create_server

    detection_profile, weight_config = parse_profile_or_path(profile)
    logger = AuditLogger(audit) if audit else None
    service = VeilService(
        pipeline=VeilPipeline(
            profile=detection_profile,
            weight_config=weight_config,
            detection_mode=detection_mode,
            audit=logger,
        ),
        session_ttl=session_ttl,
        audit=logger,
    )
    httpd = create_server(host, port, service=service)
    console.print(f"[green]Veil API listening on http://{host}:{httpd.server_address[1]}[/green]")
    console.print("  POST /anonymize  POST /reconstruct  GET /health  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if logger:
            logger.close()


@app.command(name="app")
def launch_desktop_app(
    share: bool = typer.Option(
        False,
        "--share",
        help="Create a public link",
    ),
    port: int = typer.Option(
        7860,
        "--port",
        "-p",
        help="Port to run on",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host to bind to",
    ),
) -> None:
    """Launch the Veil desktop app.

    Opens a web-based chat interface with LLM integration
    and automatic privacy protection.

    Example:
        veil app
        veil app --share  # Create public link
        veil app --port 8080
    """
    try:
        from veil.app.desktop import launch_app
    except ImportError:
        console.print("[red]Error:[/red] Desktop app dependencies not installed")
        console.print("[dim]Install with: pip install veil[desktop][/dim]")
        raise typer.Exit(1)

    console.print("[bold]Starting Veil Desktop App...[/bold]")
    console.print(f"[dim]Open http://{host}:{port} in your browser[/dim]\n")

    launch_app(share=share, server_port=port, server_name=host)


def _show_mapping_table(
    replacements: dict[str, str],
    entities: list[Any],
) -> None:
    """Display mapping table."""
    table = Table(title="Mappings")
    table.add_column("Original", style="cyan")
    table.add_column("Replacement", style="green")
    table.add_column("Type", style="dim")

    # Build type lookup
    type_lookup = {e.text: e.entity_type.value for e in entities}

    for original, replacement in replacements.items():
        entity_type = type_lookup.get(original, "unknown")
        table.add_row(original, replacement, entity_type)

    console.print(table)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """Veil - Privacy-preserving proxy for LLMs.

    Anonymize sensitive data before sending to AI models, then
    reconstruct responses with original values.

    Profiles:
      - paranoid: Maximum protection, may over-detect
      - balanced: Good tradeoff (default)
      - minimal:  Only high-confidence PII
    """
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")


if __name__ == "__main__":
    app()
