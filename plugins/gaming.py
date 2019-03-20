"""
gaming.py

Dice, coins, and random generation for gaming.

Modified By:
    - Luke Rogers <https://github.com/lukeroge>
    - leonthemisfit <https://github.com/leonthemisfit>

License:
    GPL v3
"""

import random
import re

from cloudbot import hook

# String constants for the coin flip function
INVALID_NUMBER = "Invalid input {!r}: not a number"
NO_COIN = "makes a coin flipping motion"
SINGLE_COIN = "flips a coin and gets {}."
MANY_COINS = "flips {} coins and gets {} heads and {} tails."

# Pregenerated mean and variance for fudge dice
FUDGE_MEAN = 0
FUDGE_VAR = 0.6667

INVALID_ROLL = "Invalid dice roll {!r}"

ROLL_LIMIT = 100  # The maximum number of times to roll or flip before approximating results

whitespace_re = re.compile(r'\s+')
valid_diceroll = re.compile(r'^([+-]?(?:\d+|\d*d(?:\d+|F))(?:[+-](?:\d+|\d*d(?:\d+|F)))*)( .+)?$', re.I)
sign_re = re.compile(r'[+-]?(?:\d*d)?(?:\d+|F)', re.I)
split_re = re.compile(r'([\d+-]*)d?(F|\d*)', re.I)


def find_midpoint(sides, roll_cnt):
    """find the midpoint for a die with n rolls

    :type sides: int
    :type roll_cnt: int
    :rtype: float

    >>> [find_midpoint(s, r) for s, r in [(6, 1), (6, 2), (12, 1), (12, 2)]]
    [3.5, 7, 6.5, 13]
    """
    return 0.5 * (sides + 1) * roll_cnt


def find_variance(sides):
    """find the variance for a die with n sides

    :type sides: int
    :rtype: float

    >>> [find_variance(s) for s in [3, 4, 5, 6, 20, 50]]
    [0.6667, 1.25, 2.0, 2.9167, 33.25, 208.25]
    """
    return round((sides ** 2 - 1) / 12, 4)


def find_mid_var(sides, roll_cnt):
    """find the midpoint and variance for a die with x sides and y rolls

    :type sides: int
    :type roll_cnt: int
    :rtype: (float, float)

    >>> [find_mid_var(s, r) for s, r in [(6, 1), (6, 2), (12, 1), (12, 2)]]
    [(3.5, 2.9167), (7.0, 2.9167), (6.5, 11.9167), (13.0, 11.9167)]
    """
    return find_midpoint(sides, roll_cnt), find_variance(sides)


def find_adjusted_variance(variance, roll_cnt):
    """find the variance adjusted for the number of rolls

    :type variance: float
    :type roll_cnt: int
    :rtype: float

    >>> [find_adjusted_variance(find_variance(s), r) for s, r in [(6, 1), (6, 2), (12, 1), (12, 2)]]
    [1.7078, 2.4152, 3.4521, 4.8819]
    """
    return round((variance * roll_cnt) ** 0.5, 4)


def approximate_rolls(roll_cnt, sides, fudge):
    """approximate a sum based on a random normal variate using the midpoint as the mu and variance as the sigma

    :type roll_cnt: int
    :type sides: int | str
    :type fudge: bool
    :rtype: list(int)"""
    if fudge:
        mid = FUDGE_MEAN
        var = FUDGE_VAR
    else:
        mid, var = find_mid_var(sides, roll_cnt)

    adj_var = find_adjusted_variance(var, roll_cnt)

    return [round(random.normalvariate(mid, adj_var))]


def simulate_rolls(roll_cnt, sides, fudge):
    """simulate rolling a dice

    :type roll_cnt: int
    :type sides: int | str
    :type fudge: bool
    :rtype: list(int)
    """
    if fudge:
        lower = -1
        upper = 1
    else:
        lower, upper = sorted((sides, 1))

    return [random.randint(lower, upper) for _ in range(roll_cnt)]


def n_rolls(roll_cnt, sides):
    """roll an n-sided die count times

    :type roll_cnt: int
    :type sides: int | str
    :rtype: list[int]
    """
    fudge = sides in ('f', 'F')

    if roll_cnt < ROLL_LIMIT:
        values = simulate_rolls(roll_cnt, sides, fudge)
    else:
        values = approximate_rolls(roll_cnt, sides, fudge)

    return values


@hook.command("roll", "dice")
def dice(text, notice):
    """<dice roll> - simulates dice rolls. Example: 'dice 2d20-d5+4 roll 2': D20s, subtract 1D5, add 4

    :type text: str
    """
    if hasattr(text, "groups"):
        text, desc = text.groups()
    else:  # type(text) == str
        match = valid_diceroll.match(whitespace_re.sub("", text))
        if match:
            text, desc = match.groups()
        else:
            notice(INVALID_ROLL.format(text))
            return

    if "d" not in text:
        return

    spec = whitespace_re.sub('', text)
    if not valid_diceroll.match(spec):
        notice(INVALID_ROLL.format(text))
        return
    groups = sign_re.findall(spec)

    total = 0
    rolls = []

    for roll in groups:
        count, side = split_re.match(roll).groups()
        count = int(count) if count not in " +-" else 1
        if side.upper() == "F":  # fudge dice are basically 1d3-2
            for fudge in n_rolls(count, "F"):
                if fudge == 1:
                    rolls.append("\x033+\x0F")
                elif fudge == -1:
                    rolls.append("\x034-\x0F")
                else:
                    rolls.append("0")
                total += fudge
        elif side == "":
            total += count
        else:
            side = int(side)
            try:
                if count > 0:
                    d = n_rolls(count, side)
                    rolls += list(map(str, d))
                    total += sum(d)
                else:
                    d = n_rolls(-count, side)
                    rolls += [str(-x) for x in d]
                    total -= sum(d)
            except OverflowError:
                # I have never seen this happen. If you make this happen, you win a cookie
                return "Thanks for overflowing a float, jerk >:["

    if desc:
        return "{}: {} ({})".format(desc.strip(), total, ", ".join(rolls))

    return "{} ({})".format(total, ", ".join(rolls))


@hook.command
def choose(text, event):
    """<choice1>, [choice2], [choice3], etc. - randomly picks one of the given choices

    :type text: str
    """
    choices = re.findall(r'([^,]+)', text.strip())
    if len(choices) == 1:
        choices = choices[0].split(' or ')
        if len(choices) == 1:
            event.notice_doc()
            return

    return random.choice([choice.strip() for choice in choices])


@hook.command(autohelp=False)
def coin(text, notice, action):
    """[amount] - flips [amount] coins

    :type text: str
    """
    amount = 1
    if text:
        try:
            amount = int(text)
        except (ValueError, TypeError):
            notice(INVALID_NUMBER.format(text))
            return

    if amount == 0:
        action(NO_COIN)
    elif amount == 1:
        side = random.choice(['heads', 'tails'])
        action(SINGLE_COIN.format(side))
    else:
        if amount < ROLL_LIMIT:
            heads = sum(random.randint(0, 1) for _ in range(amount))
        else:
            heads = round(amount * random.uniform(0.45, 0.55))
        tails = amount - heads
        action(MANY_COINS.format(amount, heads, tails))
