import time
import sys
import os
import textwrap
import subprocess
import re
import warnings

import praw
import requests

import curses
import curses.ascii

tags = {}


def uniq(inputlist):
    seen = set()
    seen_add = seen.add
    return [x for x in inputlist if x not in seen and not seen_add(x)]
    # top answer on https://stackoverflow.com/questions/480214/


def callprogram(program):
    subprocess.call(program, shell=True)


def extracturls(url):
    """
    Extract i.imgur.com urls from an imgur gallery
    """

    r = requests.get(url)
    data = r.text
    regex = re.compile("i\.imgur\.com.*\.jpg")
    matches = regex.findall(data)
    # Conversion to a set then a list is to remove duplicates
    matches = uniq(matches)
    matches = ["http://" + match for match in matches]
    matches = matches[:len(matches)//2]
    # Imgur returns thumbnails, which we don't want.
    return matches


def filtercomment(comment):
    """
    Given a Comment object, if this function returns False the comment will
    not be displayed, along with any subcomments
    """

    if comment.ups < comment.downs:
        return False
    return True


def printsubmission(subreddit, sub, index, stdscr, selected):
    stdscr.addstr(str(index), curses.A_BOLD)
    stdscr.addstr(": ")
    title = sub.title
    if len(str(index)) + 2 + len(sub.title) >= width:
        title = title[:width - (len(str(index)) + 3)]
    if selected:
        stdscr.addstr(title, curses.A_BOLD)
    else:
        stdscr.addstr(title)
    stdscr.addstr("\n")

    stdscr.addstr("(")
    stdscr.addstr(str(sub.ups), colours.red)

    stdscr.addstr("|")
    stdscr.addstr(str(sub.downs), colours.blue)
    stdscr.addstr(")")
    stdscr.addstr(" submitted by ")
    stdscr.addstr(str(sub.author))
    if subreddit.display_name == "all":
        stdscr.addstr(" to ")
        stdscr.addstr(sub.subreddit.display_name, colours.yellow)
    stdscr.addstr(" " + sub.domain, colours.yellow)
    stdscr.addstr("\n\n")


def updatestatusbar(screen):
    screen.addstr(0, 0, "asdf asdf adsf")


def parsecomments(comments, indentlevel=0):
    out = []
    # In the format of [indentlevel, fulltext]
    for comment in comments:
        if filtercomment(comment):
            out.append([indentlevel, comment])
            if len(comment.replies) > 0:
                for item in parsecomments(comment.replies, indentlevel+1):
                    out.append(item)

    return out


def viewcomments(submission, scr):
    comments = parsecomments(submission.comments)

    scr.clear()

    scr.addstr(submission.title + "\n")

    if submission.is_self and submission.selftext != "":
        scr.addstr(termdown(submission.selftext)+"\n")
        scr.addstr("\n")

    scr.clear()
    for index, item in enumerate(comments):
        indent = " "*(4 * item[0])
        commenttext = textwrap.fill(
            item[1].body,
            width=width,
            initial_indent=indent,
            subsequent_indent=indent)
        scr.addstr(indent + str(item[1].author), colours.yellow)
        scr.addstr("\n")
        scr.addstr(commenttext)
        scr.addstr("\n\n")


def gettags(x, tag):
    """
    Return a list of all pairs of the tag string in x.
    The output is in the format of [[start, end],..]
    The start/end is the entire string, including the tags.
    """
    tags = []
    loc = 0
    while True:
        start = x.find(tag, loc)
        if start == -1:
            break

        end = x.find(tag, start+1)
        if end == -1:
            break

        loc = end + 1
        tags.append((start, end+len(tag)))
    return tags


def termdown(body):
    # Uses the ansi() function to convert from reddit's markdown to
    # a format that can bre read in the terminal
    # gettags does not handle something like this
    # gettags(**hello** *world*, *) properly, do the longest ones first.
    return body

    bodytext = []
    for line in body.split("\n"):
        x = line
        if x.startswith("* "):
            x = u"\u2022 " + x[2:]

        if x.startswith("    "):
            x = ansi(colour.cyan, x)

        if "**" in x:
            toreplace = []
            for start, end in gettags(x, "*"):
                toreplace.append(x[start:end])

            for item in toreplace:
                x = x.replace(item, ansi(escape.underline, item[2:-2]))

        if "*" in x:
            toreplace = []
            for start, end in gettags(x, "*"):
                toreplace.append(x[start:end])

            for item in toreplace:
                x = x.replace(item, ansi(escape.underline, item[1:-1]))
        # The previous usage was wrong, as bold/italics can't be multiline
        # However, code blocks using backtick are, so they are seperate.
        bodytext.append(x)
    body = "\n".join(bodytext)

    if "`" in body:
        toreplace = []
        for start, end in gettags(body, "`"):
            toreplace.append(body[start:end])
        for item in toreplace:
            x = x.replace(item, ansi(colour.cyan, item[1:-1]))

    body = body.replace("&gt;", ">")
    return body


def refreshsubs(subreddit, sorting, timeframe, limit):
    global subs

    if sorting == "hot":
        toset = subreddit.get_hot(limit=limit)

    elif sorting == "controversial":
        if timeframe == "":
            toset = subreddit.get_controversial(limit=limit)
        elif timeframe == "hour":
            toset = subreddit.get_controversial_from_hour(limit=limit)
        elif timeframe == "day":
            toset = subreddit.get_controversial_from_day(limit=limit)
        elif timeframe == "week":
            toset = subreddit.get_controversial_from_week(limit=limit)
        elif timeframe == "month":
            toset = subreddit.get_controversial_from_month(limit=limit)
        elif timeframe == "year":
            toset = subreddit.get_controversial_from_year(limit=limit)
        elif timeframe == "all":
            toset = subreddit.get_controversial_from_all(limit=limit)
    elif sorting == "new":
        toset = subreddit.get_new(limit=limit)

    elif sorting == "rising":
        toset = subreddit.get_rising(limit=limit)

    elif sorting == "top":
        if timeframe == "":
            toset = subreddit.get_top(limit=limit)
        elif timeframe == "hour":
            toset = subreddit.get_top_from_hour(limit=limit)
        elif timeframe == "day":
            toset = subreddit.get_top_from_day(limit=limit)
        elif timeframe == "week":
            toset = subreddit.get_top_from_week(limit=limit)
        elif timeframe == "month":
            toset = subreddit.get_top_from_month(limit=limit)
        elif timeframe == "year":
            toset = subreddit.get_top_from_year(limit=limit)
        elif timeframe == "all":
            toset = subreddit.get_top_from_all(limit=limit)

    subs = list(toset)


def log(msg):
    with open("logfile", "a") as f:
        f.write("[{}]".format(time.time()))
        f.write(msg)
        f.write("\n")


def readline(screen, prompt):
    output = ""
    screen.addstr(prompt)
    while True:
        char = screen.getch()
        if char == ord("\n"):
            break
        elif char == curses.ascii.ESC:
            return ""
        elif char == curses.ascii.DEL:
            curry, currx = screen.getyx()
            if currx == 1:
                return ""
                # Trying to backspace the :
                # Just exit command mode, it's what vim does.
            screen.addstr(curry, currx-1, " ")
            screen.move(curry, currx-1)
            output = output[:-1]
        else:
            output += (chr(char))
            screen.addch(char)
    return "".join(output)
    curses.noecho()


if sys.version[0] != "3":
    sys.stderr.write("You don't seem to be using python version 3\n")
    sys.exit(0)

reddit = praw.Reddit(user_agent="command line reddit client by /u/5225225")

if len(sys.argv) >= 3:
    username = sys.argv[1]
    password = sys.argv[2]
else:
    screen.addstr("Invalid username or password")

if username == "" or password == "":
    screen.addstr("Invalid username or password")
    sys.exit(1)

try:
    with warnings.catch_warnings():
        reddit.login(username, password)
except praw.errors.InvalidUserPass:
    screen.addstr("Invalid username or password")
    sys.exit(1)


def main(screen):
    global width
    global height
    # TODO pass the screen width/height or use curses.cols/curses.rows
    global colours
    selection = 4

    class colours:
        red = curses.color_pair(1)
        green = curses.color_pair(2)
        yellow = curses.color_pair(3)
        blue = curses.color_pair(4)

    for x in range(0, 255):
        curses.init_pair(x+1, x+1, 0)

    # Once I get to this point, I can assume that the user is logged in.
    # This client can't be used without a reddit account

    subreddit = reddit.get_subreddit("python")
    sorting = "hot"
    timeframe = ""
    subheight = 3

    searchterm = ""

    width = curses.COLS
    height = curses.LINES

    statusscreen = curses.newwin(1, curses.COLS, 0, 0)
    commandline = curses.newwin(1, curses.COLS, curses.LINES-1, 0)
    limit = 100
    refreshneeded = True
    mode = "normal"
    viewing = "subs"
    line = 0

    oldselection = 0
    content = curses.newpad(5000, width)
    while True:
        posts = {}
        usableheight = height - 2
        # Reserve space for the status line and the command line
        if (refreshneeded or redrawneeded) and viewing == "subs":
            commandline.clear()
            commandline.addstr(
                "-- loading /r/{} --".format(str(subreddit)),
                curses.A_BOLD)
            commandline.refresh()
            if refreshneeded:
                refreshsubs(subreddit, sorting, timeframe, limit)
            log("Length of subs is {}".format(len(list(subs))))
            content.move(0, 0)
            for index, sub in enumerate(subs):
                if index == selection:
                    printsubmission(subreddit, sub, index, content, True)
                else:
                    printsubmission(subreddit, sub, index, content, False)
                posts[index] = sub
            commandline.clear()
            updatestatusbar(statusscreen)
            statusscreen.refresh()
            if refreshneeded:
                log("Did a full refresh")
                content.refresh(line, 0, 1, 0, height-2, width)
            else:
                log("Did a partial refresh")
                content.refresh(
                    selection*subheight,
                    0,
                    selection*subheight+1-line,
                    0,
                    selection*subheight+1-line,
                    width)

                content.refresh(
                    oldselection*subheight,
                    0,
                    oldselection*subheight+1-line,
                    0,
                    oldselection*subheight+1-line,
                    width)
            refreshneeded = False
            redrawneeded = False
            commandline.refresh()
            log("Just refreshed the content")
        # Time to add VIM modes!
        # My goal is to allow for things like <count>operator, 5j for example.
        # I'll do that after I get the basics down, though.
        try:
            mode = "normal"
            inputlist = []
            while True:
                if mode == "normal":
                    char = commandline.getch()
                    commandline.refresh()
                    if char == ord("j"):
                        if selection < 99:
                            oldselection = selection
                            selection = selection + 1
                            if selection * subheight + 2 > line + curses.LINES:
                                line = line + 3
                            redrawneeded = True
                        break

                    elif char == ord("k"):
                        if selection > 0:
                            oldselection = selection
                            selection = selection - 1
                            if selection * subheight + 2 < line:
                                line = line - 3
                            redrawneeded = True
                        break

                    elif char == ord(":"):
                        mode = "command"

                    elif char == ord("r"):
                        subredditname = readline(commandline, "r/")
                        subreddit = reddit.get_subreddit(subredditname)
                        refreshneeded = True
                        break

                    elif char == ord("\n"):
                        viewcomments(posts[selection], content)
                        commandline.clear()
                        content.refresh(line, 0, 1, 0, height-2, width)
                        viewing = "comments"
                    else:
                        pass
                if mode == "command":
                    inputstr = readline(commandline, ":").strip()
                    if inputstr == "q":
                        if viewing == "subs":
                            sys.exit()
                        elif viewing == "comments":
                            viewing = "subs"
                            refreshneeded = True
                            break
                    elif inputstr == "refresh":
                        refreshneeded = True
                        break
                    elif inputstr == "showcolours":
                        content.clear()
                        for colour in range(0, 256):
                            curses.init_pair(colour+1, colour, 0)
                            content.addstr(
                                "Colour: {}\n".format(colour),
                                curses.color_pair(colour+1))
                    commandline.erase()
                    mode = "normal"
        except KeyboardInterrupt:
            sys.exit()

curses.wrapper(main)
