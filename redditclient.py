import time
import sys
import os
import textwrap

import praw

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

def ansi(code, text):
   return "\x1b[{}m{}\x1b[m".format(code, text)

def termsize():
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
    if subreddit == "all":
        postfrom = " to {}".format(ansi(escape.underline, sub.subreddit))
    else:
        postfrom = ""

    if sub.over_18:
        title = ansi(31, title)

    line1 = "{}: {}".format(
        ansi(1,str(index)),
        title,
        )

    if len(str(index)) + len(str(title)) + 2 > width:
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
    left = "/r/{}".format(subreddit)
    right = "{} ({}:{})".format(
        username, 
        self.link_karma,
        self.comment_karma)

    spacer = " "* (width - (len(left) + len(right)))
    return "{}{}{}".format(left, spacer, right)

def parsecomments(comments, indentlevel=0):
    out = []
    # In the format of [indentlevel, fulltext]
    for comment in comments:
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
    #indentmarker = ansi(escape.bold, ansi(len(indent) % 7 + 100, " "))
    body = str("\n  ").join(textwrap.wrap(comment.body, width - (len(indent) + 2)))

    full = "{}: {} ({}|{})\n  {}\n".format(
        index,
        author,
        upvotes,
        downvotes,
        body,
        )

    return full

def viewcomments(sub):
    sub.replace_more_comments(limit=500, threshold=0)
    print("Parsing comments...")
    comments = parsecomments(sub.comments)
    outfile = open("comments", "w")
    print("Preparing to write comments...")
    towrite = []
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
    os.system("less -R comments")


def gettags(x, tag):
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
        # Haven't tested it, but something like
        # gettags(***hello**, **) will cause an infinite loop
        # and since the tags are added to a list, will eat
        # memory.
        start = x.find(tag, loc)
        if start == -1:
            break
        end = x.find(tag, start+1)
        if end == -1:
            break
        loc = end + 1
        tags.append((start,end+len(tag)))
    return tags

def termdown(body):
    # Uses the ansi() function to convert from reddit's markdown to
    # a format that can bre read in the terminal
    # gettags does not handle something like this
    # gettags(**hello** *world*, *) properly, do the longest ones first.

    if "**" in body:
        for start, end in gettags(body, "**"):
            body = body.replace(body[start:end], ansi(escape.bold, body[start+2:end-2]))

    if "*" in body:
        for start, end in gettags(body, "*"):
            body = body.replace(body[start:end], ansi(escape.underline, body[start+1:end-1]))
    if "`" in body:
        for start, end in gettags(body, "`"):
            body = body.replace(body[start:end], ansi(colour.cyan, body[start+1:end-1]))
            # You can't make text in a terminal monospaced, so making it cyan is the
            # next best thing.

            # If I were to make an HTML output format, I would make the code cleaner, by
            # giving the output the style, and let the output format figure out how to
            # format it like that.

            # An example is italic text, which URxvt doesn't support (I think konsole does)
            # Since I can't use italic text, I underline the text.
    bodytext = []
    for line in body.split("\n"):
        x = line
        if x.startswith("    "):
            x = ansi(colour.cyan, x)
        bodytext.append(x)
    body = "\n".join(bodytext)

    body = body.replace("&gt;", ">")
    return body
    

reddit = praw.Reddit(user_agent="command line reddit client by /u/5225225")

username = sys.argv[1]
password = sys.argv[2]
reddit.login(username, password)



subreddit = "python"
sorting = "hot"

subheight = 3

while True:
    width, height = termsize()
    posts = {}
    usableheight = height - 2
    # One for the top status bar, and one for the command line at the bottom.
    limit = usableheight // subheight
    blank = usableheight % subheight
    subredditobj = reddit.get_subreddit(subreddit)
    if sorting == "hot":
        submissions = subredditobj.get_hot(limit=limit)
    elif sorting == "controversial":
        submissions = subredditobj.get_controvertial(limit=limit)
    elif sorting == "new":
        submissions = subredditobj.get_new(limit=limit)
    elif sorting == "rising":
        submissions = subredditobj.get_rising(limit=limit)
    elif sorting == "top":
        submissions = subredditobj.get_top(limit=limit)
    print(statusbar())
    for _ in range(blank):
        print()
    for index, sub in enumerate(submissions):
        printsubmission(sub, index)
        posts[index] = sub
    command = input(":")
    if False: pass
    elif command.startswith("s"):
        sl = command[1]
        if sl == "h":
            sorting = "hot"

        if sl == "c":
            sorting = "controversial"

        if sl == "n":
            sorting = "new"

        if sl == "t":
            sorting = "top"

    elif command == "p":
        subfile = open("/tmp/selfpost", "w")
        contents = """<Replace this line with the post title>

Write your post here"""
        subfile.write(contents)
        subfile.close()
        os.system("vim /tmp/selfpost")
        body = open("/tmp/selfpost").read().split("\n")
        title = body[0].strip()
        content = "\n".join(body[2:])
        reddit.submit(subreddit, title, content)
    elif command.startswith("r"):
        subreddit = command[1:]
    
    elif command.startswith("o"):
        post = posts[int(command[2:])]
        if command[1] == "c":
            sys.stdout.write("Loading comments...\n")
            sub = posts[int(command[2:])]
            viewcomments(sub)
        elif command[1] == "i":
            os.system("feh -F {}".format(post.url))
        elif command[1] == "l":
            if "i.imgur.com" in post.url:
                # TODO handle imgur galleries
                # All I need to do is
                # 1. get a list of the urls
                # 2. pass that list to feh
                os.system("feh -F {}".format(post.url))
            else:
                os.system("w3m {}".format(post.url))
    elif command in ["q", "quit"]:
        sys.exit(0)
