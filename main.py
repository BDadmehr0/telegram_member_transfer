import asyncio
import json
import logging
import os
import random
import time

from rich import print as rprint
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from telethon.errors import FloodWaitError, PhoneNumberBannedError
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest

# Configure logging
logging.basicConfig(
    filename="telegram_manager.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

console = Console()
JSON_FILE = "accounts.json"


# Initialize JSON file if not exists
def initialize_json():
    if not os.path.exists(JSON_FILE):
        with open(JSON_FILE, "w") as file:
            json.dump({"api_accounts": []}, file, indent=4)


# Load JSON data
def load_data():
    with open(JSON_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# Save JSON data
def save_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# Function to check if an account is banned
async def is_account_banned(client):
    try:
        await client.get_me()
        return False
    except PhoneNumberBannedError:
        return True
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        rprint(f"[red]Unexpected error: {e}[/red]")
        return True


# Start Telegram client asynchronously
async def start_client(client, phone, index, data):
    await client.start(phone)
    if await is_account_banned(client):
        rprint("[red]This number is banned![/red]")
        logging.warning(f"Phone number {phone} is banned.")
    else:
        data["api_accounts"][index]["accounts"].append(
            {"phone": phone, "session": client.session.filename}
        )
        save_data(data)
        rprint("[green]Account added successfully![/green]")
        logging.info(f"Phone number {phone} added successfully.")


# Analyze source group and suggest transfer count
# Analyze source group and suggest transfer count
async def analyze_group(client, source_group):
    source_entity = await client.get_entity(source_group)
    members = await client.get_participants(source_entity)
    total_members = len(members)
    rprint(f"[blue]The source group has {total_members} members.[/blue]")
    
    suggested_transfer = min(total_members, 50 * len(load_data()["api_accounts"]))

    user_input = input(
        f"How many members do you want to transfer? (Recommended: {suggested_transfer} - Press Enter to accept): "
    ).strip()

    if not user_input:
        return suggested_transfer
    try:
        transfer_count = int(user_input)
        return min(transfer_count, total_members)
    except ValueError:
        rprint("[red]Invalid input! Using recommended value.[/red]")
        return suggested_transfer



# Manage Telegram accounts
def manage_accounts():
    while True:
        console.clear()
        rprint("[cyan]Account Management[/cyan]")
        options = ["Add API", "Add Account", "Remove API", "Remove Account", "Back"]
        for i, opt in enumerate(options, 1):
            rprint(f"[yellow]{i}.[/yellow] {opt}")

        choice = Prompt.ask("Choose an option")
        data = load_data()

        if choice == "1":
            api_id = Prompt.ask("API ID")
            api_hash = Prompt.ask("API Hash")
            data["api_accounts"].append(
                {"api_id": int(api_id), "api_hash": api_hash, "accounts": []}
            )
            save_data(data)
            rprint("[green]API added successfully![/green]")
        elif choice == "2":
            if not data["api_accounts"]:
                rprint("[red]No API available![/red]")
                continue
            for i, api in enumerate(data["api_accounts"], 1):
                rprint(f"{i}. API ID: {api['api_id']}")
            index = int(Prompt.ask("Select API")) - 1
            if 0 <= index < len(data["api_accounts"]):
                phone = Prompt.ask("Phone number")
                session_name = f"session_{phone[-4:]}"
                client = TelegramClient(
                    session_name,
                    data["api_accounts"][index]["api_id"],
                    data["api_accounts"][index]["api_hash"],
                )

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(start_client(client, phone, index, data))
                    else:
                        asyncio.run(start_client(client, phone, index, data))
                except RuntimeError:
                    asyncio.run(start_client(client, phone, index, data))
        elif choice == "3":  # Remove API
            if not data["api_accounts"]:
                rprint("[red]No API available to remove![/red]")
                continue
            for i, api in enumerate(data["api_accounts"], 1):
                rprint(f"{i}. API ID: {api['api_id']}")
            index = int(Prompt.ask("Select API to remove")) - 1
            if 0 <= index < len(data["api_accounts"]):
                removed_api = data["api_accounts"].pop(index)
                save_data(data)
                rprint(
                    f"[green]Removed API ID {removed_api['api_id']} successfully![/green]"
                )

        elif choice == "4":  # Remove Account
            if not data["api_accounts"]:
                rprint("[red]No API available![/red]")
                continue
            for i, api in enumerate(data["api_accounts"], 1):
                rprint(f"{i}. API ID: {api['api_id']}")
            api_index = int(Prompt.ask("Select API")) - 1
            if 0 <= api_index < len(data["api_accounts"]):
                if not data["api_accounts"][api_index]["accounts"]:
                    rprint("[red]No accounts available under this API![/red]")
                    continue
                for j, acc in enumerate(data["api_accounts"][api_index]["accounts"], 1):
                    rprint(f"{j}. Phone: {acc['phone']}")
                acc_index = int(Prompt.ask("Select account to remove")) - 1
                if 0 <= acc_index < len(data["api_accounts"][api_index]["accounts"]):
                    removed_account = data["api_accounts"][api_index]["accounts"].pop(
                        acc_index
                    )
                    save_data(data)
                    rprint(
                        f"[green]Removed account {removed_account['phone']} successfully![/green]"
                    )
        elif choice == "5":
            break
        else:
            rprint("[red]Invalid option![/red]")


async def transfer_members():
    data = load_data()
    if not data["api_accounts"]:
        rprint("[red]No API available![/red]")
        time.sleep(5)
        return

    source_groups_input = input("Enter source group(s) (comma-separated if multiple): ")
    destination_group = input("Enter destination group: ")

    # پردازش گروه‌های مبدأ
    source_groups = [group.strip() for group in source_groups_input.split(",")]

    logging.info(
        f"Starting member transfer from {', '.join(source_groups)} to {destination_group}."
    )

    clients = []
    active_accounts = []
    
    # راه‌اندازی کلاینت‌ها برای همه اکانت‌های موجود
    for api in data["api_accounts"]:
        for account in api["accounts"]:
            client = TelegramClient(account["session"], api["api_id"], api["api_hash"])
            await client.start(account["phone"])
            clients.append(client)
            active_accounts.append(account["phone"])

    if not clients:
        rprint("[red]No active accounts found![/red]")
        return

    destination_entity = await clients[0].get_entity(destination_group)
    max_invites_per_account = 50
    cooldown_time = 86400  # 24 hours in seconds
    used_accounts = {}

    # دریافت اعضای تمام گروه‌های مبدأ
    total_members_available = 0
    group_members_map = {}  # دیکشنری برای ذخیره اعضای هر گروه

    for source_group in source_groups:
        try:
            source_entity = await clients[0].get_entity(source_group)
            members = await clients[0].get_participants(source_entity)
            group_members_map[source_group] = members
            total_members_available += len(members)
        except Exception as e:
            rprint(f"[red]Error accessing group {source_group}: {e}[/red]")
            logging.error(f"Error accessing group {source_group}: {e}")
    rprint(f"[blue]Group {source_group} has {total_members_available} members.[/blue]")

    if total_members_available == 0:
        rprint("[red]No members found in the provided groups![/red]")
        return

    suggested_transfer = min(total_members_available, 50 * len(active_accounts))
    user_input = input(
        f"How many members do you want to transfer? (Recommended: {suggested_transfer}): "
    )
    transfer_count = min(int(user_input), total_members_available)

    rprint(f"[blue]Starting transfer of {transfer_count} members...[/blue]")

    transferred_count = 0
    group_cycle = list(group_members_map.keys())  # لیست گروه‌ها برای انتقال گردشی
    group_index = 0  # برای چرخش بین گروه‌ها

    while transferred_count < transfer_count:
        if not group_cycle:
            break

        current_group = group_cycle[group_index % len(group_cycle)]
        members = group_members_map[current_group]

        if not members:
            group_cycle.remove(current_group)
            continue

        member = members.pop(0)  # انتخاب اولین عضو از لیست
        client_index = transferred_count % len(clients)
        client = clients[client_index]
        phone = active_accounts[client_index]

        if phone in used_accounts and used_accounts[phone] >= max_invites_per_account:
            continue

        try:
            await client(InviteToChannelRequest(destination_entity, [member]))
            rprint(f"[green]Added {member.username or member.id} from {current_group}[/green]")
            logging.info(f"Added {member.username or member.id} from {current_group} to {destination_group}.")
            used_accounts[phone] = used_accounts.get(phone, 0) + 1
            transferred_count += 1

            delay = random.uniform(10, 30)
            rprint(f"[yellow]Waiting {delay:.2f} seconds before next request...[/yellow]")
            time.sleep(delay)

        except FloodWaitError as e:
            rprint(f"[red]Flood wait error for {phone}: Waiting {e.seconds} seconds[/red]")
            logging.warning(f"Flood wait error for {phone}: Waiting {e.seconds} seconds.")
            if e.seconds > cooldown_time:
                rprint(f"[red]{phone} is disabled for 24 hours.[/red]")
                active_accounts.remove(phone)
                clients[client_index] = None  # Disable the client
            else:
                time.sleep(e.seconds)
        except Exception as e:
            rprint(f"[red]Error: {e}[/red]")
            logging.error(f"Error adding member: {e}")

        group_index += 1  # رفتن به گروه بعدی برای انتقال

    for client in clients:
        if client:
            await client.disconnect()
    
    logging.info(f"Member transfer process completed. Total members transferred: {transferred_count}")
    rprint(f"[green]Transfer completed! Total members transferred: {transferred_count}[/green]")

# Menu to interact with the script
def menu():
    while True:
        console.clear()
        rprint("[cyan]Telegram Account Manager[/cyan]")
        options = ["Manage Accounts", "Transfer Members", "Exit"]
        for i, opt in enumerate(options, 1):
            rprint(f"[yellow]{i}.[/yellow] {opt}")

        choice = Prompt.ask("Choose an option")
        if choice == "1":
            manage_accounts()
        elif choice == "2":
            asyncio.run(transfer_members())
        elif choice == "3":
            rprint("[yellow]Exiting...[/yellow]")
            logging.info("User exited the application.")
            break
        else:
            rprint("[red]Invalid option![/red]")
            time.sleep(2)


initialize_json()
menu()
