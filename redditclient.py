import time
import sys
import os
import textwrap
import subprocess
import re

import praw
import requests

class escape:
    reset = 0
    bold = 1
    underline = 4
    blink = 5


class colour:
    black = 30
    red = 31
    green = 32
    yellow = 33
    blue = 34
    cyan = 36

    bg_red = 41
    bg_green = 42
    bg_yellow = 43
    bg_blue = 45
    bg_cyan = 46
    bg_white = 47


def uniq(inputlist):
    seen = set()
    seen_add = seen.add
    return [x for x in inputlist if x not in seen and not seen_add(x)]
    # top answer on https://stackoverflow.com/questions/480214/

def callprogram(program):
    try:
        subprocess.call(program, shell=True)
    except FileNotFoundError:
        print("{} can't be found on your system, install it".format(program))


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

def promptpassword(prompt):
    callprogram("stty -echo")
    try:
        password = input(prompt)
    except KeyboardInterrupt:
        callprogram("stty echo")
        print()
        quit()
    callprogram("stty echo")
    print()
    return password


def ansilen(text):
    """
    Return the length of a string, taking into account ANSI escape codes
    """
    length = 0
    ignore = False
    for letter in text:
        if letter == "\x1b":
            ignore = True
        if not ignore:
            length = length + 1
        if ignore and letter == "m":
            ignore = False
    return length


def ansi(code, text):
    """
    Return an ANSI SGR code, using the code and the text.
    """
    return "\x1b[{}m{}\x1b[m".format(code, text)


def filtercomment(comment):
    """
    Given a Comment object, if this function returns False the comment will
    not be displayed, along with any subcomments
    """

    if comment.ups < comment.downs:
        return False
    return True


def termsize():
    """
    Return the terminal size as a list, [height, width]
    """
    sizeproc = os.popen("stty size")
    width, height = sizeproc.read().split()
    sizeproc.close()
    return [int(height), int(width)]


def printsubmission(sub, index):
    title = sub.title
    upvotes = ansi(colour.red, sub.ups)
    downvotes = ansi(colour.blue, sub.downs)
    poster = ansi(escape.underline, str(sub.author))
    comments = ansi(escape.underline, sub.num_comments)

    if subreddit.display_name == "all":
        postfrom = " to {}".format(ansi(
            escape.underline,
            sub.subreddit.display_name))
    else:
        postfrom = ""

    if sub.over_18:
        title = ansi(31, title)

    line1 = "{}: {}".format(
        ansi(1, str(index)),
        title,
        )

    if ansilen(line1) > width:
        line1 = line1[:width-1] + u"\u2026"

    domain = ansi(colour.yellow, sub.domain)

    line2 = "({}|{}) submitted by {}{}, with {} comments ({})".format(
        upvotes,
        downvotes,
        poster,
        postfrom,
        comments,
        domain,
        )

    line3 = ""
    sys.stdout.write("{}\n{}\n{}\n".format(line1, line2, line3))


def statusbar():
    self = reddit.get_redditor(username)
    if sorting in ["controversial", "top"]:
        timestr = "/{}".format(timeframe)
    else:
        timestr = ""
    left = "/r/{}/{}{}".format(subreddit.display_name, sorting, timestr)
    right = "{} ({}:{})".format(
        username,
        self.link_karma,
        self.comment_karma)

    spacer = " " * (width - (ansilen(left) + ansilen(right)))
    return "{}{}{}".format(left, spacer, right)


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


def formatcomment(subauthor, comment, index, indent):
    index = ansi(escape.bold, index)

    if subauthor == str(comment.author):
        author = ansi(colour.cyan, ansi(escape.bold, comment.author))
    else:
        author = comment.author

    upvotes = ansi(colour.red, comment.ups)
    downvotes = ansi(colour.blue, comment.downs)
    body = str("\n  ").join(textwrap.wrap(
        comment.body,
        width - (len(indent) + 2)))

    full = "{}: {} ({}|{})\n  {}\n".format(
        index,
        author,
        upvotes,
        downvotes,
        body,
        )

    return full


def viewcomments(sub):
    sub.replace_more_comments(limit=4, threshold=0)
    print("Parsing comments...")
    comments = parsecomments(sub.comments)
    outfile = open("comments", "w")

    print("Preparing to write comments...")
    towrite = [sub.title, ""]

    if sub.is_self and sub.selftext != "":
        towrite.append(termdown(sub.selftext))
        towrite.append("")

    x = str(sub.author)

    for index, item in enumerate(comments):
        indent = " "*(4 * item[0])
        print("Formatting comment {} out of {}".format(index+1, len(comments)))
        for line in formatcomment(x, item[1], index, indent).split("\n"):
            towrite.append(indent + termdown(line))

    print("Writing comments...")
    outfile.write("\n".join(towrite))
    outfile.close()

    print("Opening comments...")
    callprogram("less -R comments")


def gettags(x, tag):
    """
    Return a list of all pairs of the tag string in x.

    The output is in the format of [[start, end],..]
    The start/end is the entire string, including the tags.
    """
    tags = []
    loc = 0
    safetycounter = 100
    while True:
        safetycounter -= 1
        if safetycounter < 0:
            sys.stderr.write("ERR: Safety counter reached in gettags!\n")
            with open("errfile", "a") as errfile:
                errfile.write("ERR: SAFETY COUNTER\n")
                errfile.write(x + "\n")
                errfile.write("TAG: {}\n---\n\n".format(tag))
            return []
            break

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


if sys.version[0] != "3":
    print("You don't seem to be using python version 3")
    sys.exit(0)

reddit = praw.Reddit(user_agent="command line reddit client by /u/5225225")

if len(sys.argv) == 1:
    username = input("Enter username: ")
    password = promptpassword("Enter password: ")
elif len(sys.argv) == 2:
    username = sys.argv[1]
    password = promptpassword("Enter password: ")
else:
    username = sys.argv[1]
    password = sys.argv[2]

if username == "" or password == "":
    print("Invalid username or password")
    sys.exit(1)

try:
    reddit.login(username, password)
except praw.errors.InvalidUserPass:
    print("Invalid username or password")
    sys.exit(1)

# Once I get to this point, I can assume that the user is logged in.
# This client can't be used without a reddit account

subreddit = reddit.get_subreddit("python")
sorting = "hot"
timeframe = ""
subheight = 3


while True:
    width, height = termsize()
    posts = {}
    usableheight = height - 2
    # One for the top status bar, and one for the command line at the bottom.
    limit = usableheight // subheight
    blank = usableheight % subheight
    if sorting == "hot":
        subs = subreddit.get_hot(limit=limit)

    elif sorting == "controversial":
        if timeframe == "":
            subs = subreddit.get_controversial(limit=limit)
        elif timeframe == "hour":
            subs = subreddit.get_controversial_from_hour(limit=limit)
        elif timeframe == "day":
            subs = subreddit.get_controversial_from_day(limit=limit)
        elif timeframe == "week":
            subs = subreddit.get_controversial_from_week(limit=limit)
        elif timeframe == "month":
            subs = subreddit.get_controversial_from_month(limit=limit)
        elif timeframe == "year":
            subs = subreddit.get_controversial_from_year(limit=limit)
        elif timeframe == "all":
            subs = subreddit.get_controversial_from_all(limit=limit)
    elif sorting == "new":
        subs = subreddit.get_new(limit=limit)

    elif sorting == "rising":
        subs = subreddit.get_rising(limit=limit)

    elif sorting == "top":
        if timeframe == "":
            subs = subreddit.get_top(limit=limit)
        elif timeframe == "hour":
            subs = subreddit.get_top_from_hour(limit=limit)
        elif timeframe == "day":
            subs = subreddit.get_top_from_day(limit=limit)
        elif timeframe == "week":
            subs = subreddit.get_top_from_week(limit=limit)
        elif timeframe == "month":
            subs = subreddit.get_top_from_month(limit=limit)
        elif timeframe == "year":
            subs = subreddit.get_top_from_year(limit=limit)
        elif timeframe == "all":
            subs = subreddit.get_top_from_all(limit=limit)

    print(statusbar())
    for _ in range(blank):
        print()
    for index, sub in enumerate(subs):
        printsubmission(sub, index)
        posts[index] = sub
    command = input(":")
    if command.startswith("s"):
        sl = command[1]

        needs_time = True

        if sl == "h":
            sorting = "hot"
            needs_time = False

        if sl == "c":
            sorting = "controversial"

        if sl == "n":
            sorting = "new"
            needs_time = False

        if sl == "t":
            sorting = "top"

        if needs_time:
            if command[2] == "h":
                timeframe = "hour"

            if command[2] == "d":
                timeframe = "day"

            if command[2] == "w":
                timeframe = "week"

            if command[2] == "m":
                timeframe = "month"

            if command[2] == "y":
                timeframe = "year"

            if command[2] == "a":
                timeframe = "all"

    elif command == "p":
        subfile = open("/tmp/selfpost", "w")
        contents = """<Replace this line with the post title>

Write your post here"""
        subfile.write(contents)
        subfile.close()
        callprogram("vim /tmp/selfpost")
        body = open("/tmp/selfpost").read().split("\n")
        title = body[0].strip()
        content = "\n".join(body[2:])
        reddit.submit(subreddit, title, content)
    elif command.startswith("r"):
        subreddit = reddit.get_subreddit(command[1:], fetch=True)
        

    elif command.startswith("o"):
        post = posts[int(command[2:])]
        if command[1] == "c":
            sys.stdout.write("Loading comments...\n")
            sub = posts[int(command[2:])]
            viewcomments(sub)
        elif command[1] == "i":
            callprogram("feh -F {}".format(post.url))
        elif command[1] == "l":
            if "i.imgur.com" in post.url:
                callprogram("feh -F {}".format(post.url))
            if "imgur.com" in post.url:
                urls = extracturls(post.url)
                callprogram("feh -F {}".format(" ".join(urls)))
            elif "youtube.com" in post.url:
                callprogram("vlc -f {}".format(post.url))
            else:
                callprogram("w3m {}".format(post.url))
    elif command == "desc":
        outfile = open("sidebar", "w")
        sidebar = termdown(subreddit.description)
        outfile.write(sidebar)
        outfile.close()
        callprogram("less -R sidebar")
    elif command == "help":
        print("I haven't written a manual yet. In the mean time, read")
        print("the source code. (hit enter to return)")
        input()
    elif command == "pdbstart":
        import pdb
        pdb.set_trace()
    elif command in ["q", "quit"]:
        sys.exit(0)
