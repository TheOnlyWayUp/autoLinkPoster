""""Program to check for messages in a channel containing a URL and Description, adding that to a database and periodically sending one of those cool links to the #cool links channel on the r/discord_bots discord server."""

# pylint: disable=invalid-name, wrong-import-order, multiple-imports, no-member

import discord, aiosqlite, yaml, re, discord_colorize, datetime
from typing import List, Dict
from discord.ext import commands, tasks
from rich.console import Console

# --- Constants --- #

bot = commands.Bot(command_prefix=">", self_bot=True, case_insensitive=True)
bot.colors = discord_colorize.Colors()
bot.databasePath = "database.db"
bot.console = Console()
bot.urlRegex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
bot.titleRegex = r"(?<=Title:)(.*)(?=\n)"
bot.descriptionRegex = r"(?<=Desc:)(.*)(?=\n)"
with open("config.yml", "r", encoding="utf-8") as configFile:
    config = yaml.safe_load(configFile)
configCopy = config.copy()
for key, value in configCopy.items():
    if isinstance(value, str):
        try:
            config[key] = int(value)
        except ValueError:
            pass
bot.config = config

# --- Functions --- #


async def readyDatabase() -> bool:
    """Checks if the database is ready to be used. Else creates a database - username: str, id: int, title: str, description: str, url: str, date_added: str, sent: bool

    Returns:
        Boolean: [description]
    """
    async with aiosqlite.connect(bot.databasePath) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS links(
            username TEXT,
            id INTEGER,
            title TEXT,
            description TEXT,
            url TEXT,
            date_added TEXT,
            sent BOOLEAN
        )"""
        )
        await db.commit()
        return True


def findURLs(string: str) -> List[str]:
    """Finds all URLs in a string and returns them as a list.

    Args:
        string (str): The string to search for URLs in.

    Returns:
        List[str]: A list of URLs found in the string.
    """
    url = re.findall(bot.urlRegex, string)
    return [Url[0] for Url in url]


def returnInfo(string: str) -> Dict[str, str]:
    """Finds the title and description in a string and returns them as a dictionary.

    Args:
        string (str): The string to search for the title and description in.

    Returns:
        Dict[str, str]: A dictionary containing the title and description.
    """
    title = re.findall(bot.titleRegex, string)
    description = re.findall(bot.descriptionRegex, string)
    return {"title": title[0], "description": description[0]}


# --- Events --- #


@bot.event
async def on_ready() -> None:
    """Event called when the bot is ready."""
    bot.console.log(
        f"Logged in [green]successfully[/green] as [blue]{bot.user}[/blue]."
    )
    # await returnConfig()
    bot.console.log("The config file was loaded [green]successfully[/green].")
    await readyDatabase()
    bot.console.log("The database was loaded [green]successfully[/green].")


@bot.event
async def on_message(message: discord.Message) -> None:
    """Event called when a message is sent in a channel.

    Args:
        message (discord.Message): The message that was sent in a channel.
    """
    if message.channel.id != bot.config["submissionChannel"]:
        return
    if message.author.id == bot.user.id:
        return
    # example - {bot.colors.colorize('Hello World!', fg='green', bg='indigo', bold=True, underline=True)}
    replyMessage = await message.reply(
        f"Thank you for your contribution.\n\n```ansi\n{bot.colors.colorize('STATUS:', fg='green', bold=True)} {bot.colors.colorize('Processing...', fg='yellow', underline=True)}\n```"
    )
    links = findURLs(message.content)
    if len(links) == 0:
        await replyMessage.edit(
            content=f"```ansi\n{bot.colors.colorize('STATUS:', fg='red', bold=True)} {bot.colors.colorize('No links found. Stopping.', fg='red', underline=True)}\n```"
        )
        return
    info = returnInfo(message.content)
    if info["title"] == "":
        await replyMessage.edit(
            content=f"```ansi\n{bot.colors.colorize('STATUS:', fg='red', bold=True)} {bot.colors.colorize('No title found. Stopping.', fg='red', underline=True)}\n```"
        )
        return
    if info["description"] == "":
        await replyMessage.edit(
            content=f"```ansi\n{bot.colors.colorize('STATUS:', fg='red', bold=True)} {bot.colors.colorize('No description found. Stopping.', fg='red', underline=True)}\n```"
        )
        return
    title = info["title"]
    description = info["description"]
    url = links[0]
    del links, info
    depthString = "\n\nTitle: {}\nDesc: {}\nURL: {}".format(title, description, url)
    await replyMessage.edit(
        content=f"```ansi\n{bot.colors.colorize('STATUS:', fg='green', bold=True)} {bot.colors.colorize(f'Processing...{depthString}', fg='yellow', underline=True)}\n```"
    )
    async with aiosqlite.connect(bot.databasePath) as db:
        await db.execute(
            """INSERT INTO links(username, id, title, description, url, date_added, sent) VALUES(?,?,?,?,?,?,?)""",
            (
                f"{message.author.name}#{message.author.discriminator}",
                message.author.id,
                title,
                description,
                url,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                False,
            ),
        )
        await db.commit()
    await replyMessage.edit(
        content=f"```ansi\n{bot.colors.colorize('STATUS:', fg='green', bold=True)} {bot.colors.colorize(f'Added to database!{depthString}', fg='green', underline=True)}\n```"
    )


# --- Tasks --- #


@tasks.loop(minutes=bot.config["sendingDelay"])
async def sendLinks() -> None:
    """
    Task that sends links from the database to the submission channel."""
    bot.console.log("Sending random suggestion.")
    async with aiosqlite.connect(bot.databasePath) as db:
        link = await db.execute(
            """SELECT * FROM links WHERE sent = 0 ORDER BY RANDOM() LIMIT 1"""
        )
        link = await link.fetchone()
        if link is None:
            bot.console.log("No links to send.")
            return
        channel = bot.get_channel(bot.config["suggestionChannel"])
        author = link[1]
        authorId = link[2]
        title = link[3]
        description = link[4]
        url = link[5]
        date = link[6]
        date = date.strftime("%Y-%m-%d %H:%M:%S")

        toSend = f"""```ansi\n{bot.colors.colorize('Cool Link: ', fg='green', bold=True)} {bot.colors.colorize(title, fg='yellow', underline=True)}```\n{description}\nURL: {url}\nOther Information: {author} (<@{authorId})>), {date}."""
        await channel.send(toSend)

        await db.execute("""UPDATE links SET sent = 1 WHERE id = ?""", (link[1],))
        await db.commit()
        bot.console.log(f"Sent link {url}.")


# --- Running --- #

if __name__ == "__main__":
    bot.run(bot.config["token"])
