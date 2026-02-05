"""Command-line interface for the Personal Outreach Agent."""

import json
import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich import box

from .config import get_settings, PROJECT_ROOT
from .database import init_db, get_db_session, reset_db
from .models.lead import Lead, LeadStatus, Segment, Region
from .models.outreach import OutreachMessage, MessageVariant, MessageStatus
from .services.lead_finder import LeadFinder, generate_sample_leads
from .services.segmenter import LeadSegmenter
from .services.personalizer import Personalizer
from .services.outreach_writer import OutreachWriter
from .services.planner import OutreachPlanner
from .utils.deduplicator import LeadDeduplicator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich console for pretty output
console = Console()


@click.group()
@click.option('--debug/--no-debug', default=False, help='Enable debug logging')
def cli(debug):
    """Personal Outreach Agent for Common Notary Apostille.

    A tool for managing attorney outreach campaigns with personalization.
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
def init():
    """Initialize the database."""
    with console.status("[bold green]Initializing database..."):
        init_db()
    console.print("[green]Database initialized successfully!")


@cli.command()
@click.confirmation_option(prompt='This will delete all data. Are you sure?')
def reset():
    """Reset the database (deletes all data)."""
    reset_db()
    console.print("[yellow]Database has been reset.")


@cli.command()
def demo():
    """Load sample data and demonstrate the system."""
    console.print(Panel.fit(
        "[bold blue]Personal Outreach Agent Demo[/bold blue]\n"
        "Loading sample attorney leads and generating outreach emails.",
        border_style="blue"
    ))

    # Initialize database
    with console.status("[bold green]Initializing database..."):
        init_db()

    with get_db_session() as session:
        # Check if we already have leads
        existing_count = session.query(Lead).count()
        if existing_count > 0:
            if not click.confirm(f"Database has {existing_count} existing leads. Add more sample data?"):
                console.print("[yellow]Using existing data.")
            else:
                _load_sample_data(session)
        else:
            _load_sample_data(session)

        # Show stats
        _show_pipeline_stats(session)

        # Generate daily plan
        console.print("\n[bold]Daily Outreach Plan:[/bold]")
        planner = OutreachPlanner(session)
        plan = planner.generate_daily_plan()

        if plan.total_count == 0:
            console.print("[yellow]No leads ready for outreach. Run 'outreach-agent leads list' to see all leads.")
        else:
            _display_daily_plan(plan)

        session.commit()


def _load_sample_data(session):
    """Load sample data into the database."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        # Load sample leads
        task = progress.add_task("Loading sample leads...", total=None)
        finder = LeadFinder()
        sample_data = generate_sample_leads()
        leads = finder.import_from_json(sample_data)

        # Get existing leads for deduplication
        existing = session.query(Lead).all()
        deduper = LeadDeduplicator(existing)
        unique_leads, duplicates = deduper.deduplicate_list(leads)

        progress.update(task, description=f"Found {len(unique_leads)} unique leads, {len(duplicates)} duplicates")

        # Add unique leads to session
        for lead in unique_leads:
            session.add(lead)
        session.flush()  # Get IDs assigned

        # Segment leads
        progress.update(task, description="Segmenting leads...")
        segmenter = LeadSegmenter()
        segmenter.segment_leads(unique_leads)

        # Generate personalization (skip for demo - would require real websites)
        progress.update(task, description="Setting up personalization...")
        for lead in unique_leads:
            # Use fallback personalization for demo
            personalizer = Personalizer()
            lead.personalization_snippet = personalizer.generate_fallback_snippet(lead)

        # Generate outreach messages
        progress.update(task, description="Generating outreach emails...")
        writer = OutreachWriter()
        writer.generate_messages_for_leads(unique_leads, session)

        # Update lead status to ready
        for lead in unique_leads:
            lead.status = LeadStatus.READY

        progress.update(task, description=f"[green]Loaded {len(unique_leads)} leads with outreach emails!")

    console.print(f"\n[green]Successfully loaded {len(unique_leads)} sample leads!")
    if duplicates:
        console.print(f"[yellow]Skipped {len(duplicates)} duplicate leads.")


def _show_pipeline_stats(session):
    """Display pipeline statistics."""
    planner = OutreachPlanner(session)
    stats = planner.get_pipeline_stats()

    table = Table(title="Pipeline Statistics", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Total Leads", str(stats.get("total_leads", 0)))
    table.add_row("Leads with Email", str(stats.get("leads_with_email", 0)))
    table.add_row("", "")
    table.add_row("[bold]By Status[/bold]", "")
    table.add_row("  New", str(stats.get("leads_new", 0)))
    table.add_row("  Ready", str(stats.get("leads_ready", 0)))
    table.add_row("  In Outreach", str(stats.get("leads_in_outreach", 0)))
    table.add_row("  Replied", str(stats.get("leads_replied", 0)))
    table.add_row("  Booked", str(stats.get("leads_booked", 0)))
    table.add_row("", "")
    table.add_row("[bold]By Region[/bold]", "")
    table.add_row("  DC", str(stats.get("region_DC", 0)))
    table.add_row("  NoVA", str(stats.get("region_NoVA", 0)))
    table.add_row("  SWVA", str(stats.get("region_SWVA", 0)))

    console.print(table)


def _display_daily_plan(plan):
    """Display the daily outreach plan."""
    table = Table(title=f"Outreach Queue for {plan.date.strftime('%Y-%m-%d')}", box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("Type", width=10)
    table.add_column("Lead", style="cyan")
    table.add_column("Email", style="green")
    table.add_column("Segment", width=15)
    table.add_column("Region", width=8)
    table.add_column("Priority", justify="right", width=8)

    for i, item in enumerate(plan.all_items, 1):
        msg_type = "INTRO" if item.message.variant == MessageVariant.INTRO else item.message.variant.value.upper()
        table.add_row(
            str(i),
            msg_type,
            item.lead.display_name[:30],
            item.lead.attorney_email or "-",
            item.lead.segment.value if item.lead.segment else "-",
            item.lead.region.value if item.lead.region else "-",
            str(item.priority)
        )

    console.print(table)
    console.print(f"\nTotal: {plan.total_count} emails ({len(plan.intro_queue)} intros, {len(plan.followup_queue)} follow-ups)")


# Lead management commands
@cli.group()
def leads():
    """Manage leads."""
    pass


@leads.command('list')
@click.option('--status', type=click.Choice([s.value for s in LeadStatus]), help='Filter by status')
@click.option('--region', type=click.Choice([r.value for r in Region]), help='Filter by region')
@click.option('--segment', type=click.Choice([s.value for s in Segment]), help='Filter by segment')
@click.option('--limit', default=50, help='Maximum number of leads to show')
def list_leads(status, region, segment, limit):
    """List all leads."""
    init_db()

    with get_db_session() as session:
        query = session.query(Lead)

        if status:
            query = query.filter(Lead.status == LeadStatus(status))
        if region:
            query = query.filter(Lead.region == Region(region))
        if segment:
            query = query.filter(Lead.segment == Segment(segment))

        query = query.order_by(Lead.created_at.desc()).limit(limit)
        leads = query.all()

        if not leads:
            console.print("[yellow]No leads found.")
            return

        table = Table(title=f"Leads ({len(leads)} shown)", box=box.ROUNDED)
        table.add_column("ID", style="dim", width=4)
        table.add_column("Firm", style="cyan", max_width=25)
        table.add_column("Attorney", max_width=20)
        table.add_column("Email", style="green", max_width=30)
        table.add_column("Status", width=12)
        table.add_column("Segment", width=15)
        table.add_column("Region", width=8)

        for lead in leads:
            table.add_row(
                str(lead.id),
                lead.firm_name[:25] if lead.firm_name else "-",
                lead.attorney_name[:20] if lead.attorney_name else "-",
                lead.attorney_email[:30] if lead.attorney_email else "-",
                lead.status.value if lead.status else "-",
                lead.segment.value if lead.segment else "-",
                lead.region.value if lead.region else "-"
            )

        console.print(table)


@leads.command('show')
@click.argument('lead_id', type=int)
def show_lead(lead_id):
    """Show details for a specific lead."""
    init_db()

    with get_db_session() as session:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()

        if not lead:
            console.print(f"[red]Lead {lead_id} not found.")
            return

        console.print(Panel.fit(
            f"[bold]{lead.firm_name}[/bold]\n"
            f"Attorney: {lead.attorney_name or 'N/A'}\n"
            f"Email: {lead.attorney_email or 'N/A'}\n"
            f"Phone: {lead.attorney_phone or 'N/A'}\n"
            f"City: {lead.city or 'N/A'}, {lead.state or ''}\n"
            f"Website: {lead.firm_website or 'N/A'}\n\n"
            f"Status: {lead.status.value if lead.status else 'N/A'}\n"
            f"Segment: {lead.segment.value if lead.segment else 'N/A'}\n"
            f"Region: {lead.region.value if lead.region else 'N/A'}\n"
            f"Confidence: {lead.confidence_score:.2f}\n\n"
            f"Practice Areas: {lead.practice_areas or 'N/A'}\n"
            f"Source: {lead.source_name or 'N/A'}\n"
            f"Notes: {lead.notes or 'N/A'}",
            title=f"Lead #{lead.id}",
            border_style="blue"
        ))

        if lead.personalization_snippet:
            console.print(Panel(
                lead.personalization_snippet,
                title="Personalization Snippet",
                border_style="green"
            ))

        # Show outreach messages
        messages = session.query(OutreachMessage).filter(
            OutreachMessage.lead_id == lead_id
        ).all()

        if messages:
            console.print("\n[bold]Outreach Messages:[/bold]")
            for msg in messages:
                status_color = {
                    MessageStatus.DRAFT: "yellow",
                    MessageStatus.APPROVED: "blue",
                    MessageStatus.SENT: "green",
                    MessageStatus.REPLIED: "cyan"
                }.get(msg.status, "white")

                console.print(f"  [{status_color}]{msg.variant.value}[/{status_color}]: {msg.status.value}")


@leads.command('add')
@click.option('--firm', required=True, help='Firm name')
@click.option('--attorney', help='Attorney name')
@click.option('--email', help='Email address')
@click.option('--phone', help='Phone number')
@click.option('--city', help='City')
@click.option('--state', help='State')
@click.option('--website', help='Firm website')
@click.option('--practice-areas', help='Practice areas (comma-separated)')
@click.option('--source', default='manual', help='Source name')
@click.option('--notes', help='Additional notes')
def add_lead(firm, attorney, email, phone, city, state, website, practice_areas, source, notes):
    """Add a new lead manually."""
    init_db()

    with get_db_session() as session:
        finder = LeadFinder()
        areas = [a.strip() for a in practice_areas.split(',')] if practice_areas else None

        lead = finder.create_lead_manual(
            firm_name=firm,
            attorney_name=attorney,
            attorney_email=email,
            attorney_phone=phone,
            city=city,
            state=state,
            website=website,
            practice_areas=areas,
            source_name=source,
            notes=notes
        )

        # Check for duplicates
        existing = session.query(Lead).all()
        deduper = LeadDeduplicator(existing)
        is_dup, matched, reason = deduper.is_duplicate(lead)

        if is_dup:
            console.print(f"[yellow]Warning: This lead appears to be a duplicate of '{matched.display_name}' ({reason})")
            if not click.confirm("Add anyway?"):
                return

        # Segment the lead
        segmenter = LeadSegmenter()
        segmenter.segment_lead(lead)

        session.add(lead)
        session.commit()

        console.print(f"[green]Lead added successfully with ID {lead.id}")


@leads.command('import')
@click.argument('file_path', type=click.Path(exists=True))
def import_leads(file_path):
    """Import leads from a JSON or CSV file."""
    init_db()

    path = Path(file_path)

    with get_db_session() as session:
        finder = LeadFinder()

        if path.suffix.lower() == '.json':
            with open(path) as f:
                data = json.load(f)
            leads = finder.import_from_json(data)
        elif path.suffix.lower() == '.csv':
            with open(path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            leads = finder.import_from_csv_rows(rows)
        else:
            console.print(f"[red]Unsupported file format: {path.suffix}")
            return

        # Deduplicate
        existing = session.query(Lead).all()
        deduper = LeadDeduplicator(existing)
        unique, duplicates = deduper.deduplicate_list(leads)

        # Segment leads
        segmenter = LeadSegmenter()
        segmenter.segment_leads(unique)

        # Add to database
        for lead in unique:
            session.add(lead)

        session.commit()

        console.print(f"[green]Imported {len(unique)} leads ({len(duplicates)} duplicates skipped)")


# Outreach commands
@cli.group()
def outreach():
    """Manage outreach campaigns."""
    pass


@outreach.command('generate')
@click.option('--lead-id', type=int, help='Generate for specific lead')
@click.option('--status', type=click.Choice(['new', 'researched', 'ready']), default='ready',
              help='Generate for leads with this status')
def generate_messages(lead_id, status):
    """Generate outreach email variants for leads."""
    init_db()

    with get_db_session() as session:
        writer = OutreachWriter()

        if lead_id:
            lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                console.print(f"[red]Lead {lead_id} not found.")
                return
            leads = [lead]
        else:
            status_enum = LeadStatus(status)
            leads = session.query(Lead).filter(
                Lead.status == status_enum,
                Lead.attorney_email.isnot(None)
            ).all()

        if not leads:
            console.print("[yellow]No leads found matching criteria.")
            return

        with Progress(console=console) as progress:
            task = progress.add_task("Generating emails...", total=len(leads))

            for lead in leads:
                # Check if messages already exist
                existing = session.query(OutreachMessage).filter(
                    OutreachMessage.lead_id == lead.id
                ).count()

                if existing == 0:
                    writer.generate_messages_for_leads([lead], session)
                    lead.status = LeadStatus.READY

                progress.advance(task)

        session.commit()
        console.print(f"[green]Generated outreach emails for {len(leads)} leads.")


@outreach.command('preview')
@click.argument('lead_id', type=int)
@click.option('--variant', type=click.Choice(['intro', 'followup_1', 'followup_2']), default='intro')
def preview_message(lead_id, variant):
    """Preview an outreach email for a lead."""
    init_db()

    with get_db_session() as session:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            console.print(f"[red]Lead {lead_id} not found.")
            return

        writer = OutreachWriter()
        variant_enum = MessageVariant(variant)
        subject, body = writer.preview_email(lead, variant_enum)

        console.print(Panel.fit(
            f"[bold]To:[/bold] {lead.attorney_email or 'N/A'}\n"
            f"[bold]Subject:[/bold] {subject}\n\n"
            f"{body}",
            title=f"Email Preview: {variant.upper()}",
            border_style="blue"
        ))


@outreach.command('plan')
def show_plan():
    """Show today's outreach plan."""
    init_db()

    with get_db_session() as session:
        planner = OutreachPlanner(session)
        plan = planner.generate_daily_plan()

        if plan.total_count == 0:
            console.print("[yellow]No outreach scheduled for today.")
            console.print("Run 'outreach-agent outreach generate' to create emails for ready leads.")
            return

        _display_daily_plan(plan)


@outreach.command('approve')
@click.argument('message_id', type=int)
def approve_message(message_id):
    """Approve a message for sending (human-in-the-loop)."""
    init_db()

    with get_db_session() as session:
        message = session.query(OutreachMessage).filter(
            OutreachMessage.id == message_id
        ).first()

        if not message:
            console.print(f"[red]Message {message_id} not found.")
            return

        # Show the message
        lead = message.lead
        console.print(Panel.fit(
            f"[bold]To:[/bold] {lead.attorney_email}\n"
            f"[bold]Subject:[/bold] {message.subject}\n\n"
            f"{message.body}",
            title=f"Message #{message_id} ({message.variant.value})",
            border_style="yellow"
        ))

        if click.confirm("Approve this message for sending?"):
            planner = OutreachPlanner(session)
            planner.mark_message_approved(message)
            session.commit()
            console.print("[green]Message approved!")
        else:
            console.print("[yellow]Message not approved.")


@outreach.command('mark-sent')
@click.argument('message_id', type=int)
def mark_sent(message_id):
    """Mark a message as sent (after manually sending)."""
    init_db()

    with get_db_session() as session:
        message = session.query(OutreachMessage).filter(
            OutreachMessage.id == message_id
        ).first()

        if not message:
            console.print(f"[red]Message {message_id} not found.")
            return

        planner = OutreachPlanner(session)
        planner.mark_message_sent(message)
        session.commit()
        console.print(f"[green]Message {message_id} marked as sent.")


@outreach.command('stats')
def show_stats():
    """Show outreach statistics."""
    init_db()

    with get_db_session() as session:
        _show_pipeline_stats(session)


# Export command
@cli.command()
@click.argument('output_file', type=click.Path())
@click.option('--format', 'fmt', type=click.Choice(['json', 'csv']), default='json')
def export(output_file, fmt):
    """Export leads and messages to a file."""
    init_db()

    with get_db_session() as session:
        leads = session.query(Lead).all()

        data = []
        for lead in leads:
            lead_data = lead.to_dict()

            # Add messages
            messages = session.query(OutreachMessage).filter(
                OutreachMessage.lead_id == lead.id
            ).all()

            lead_data['messages'] = [msg.to_dict() for msg in messages]
            data.append(lead_data)

        path = Path(output_file)

        if fmt == 'json':
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        else:
            # Flatten for CSV
            if data:
                with open(path, 'w', newline='') as f:
                    # Get all keys from first item (excluding nested messages)
                    fieldnames = [k for k in data[0].keys() if k != 'messages']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for item in data:
                        row = {k: v for k, v in item.items() if k != 'messages'}
                        writer.writerow(row)

        console.print(f"[green]Exported {len(data)} leads to {output_file}")


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()
