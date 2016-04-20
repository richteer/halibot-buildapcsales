import re
import tokenize
from io import StringIO
import itertools
import logging

# GRAMMAR:
# S	      ::= CLAUSES END
# CLAUSES ::= CLAUSE CLAUSES | e
# CLAUSE  ::= accept COND | reject COND
# COND    ::= SCOND and COND | SCOND
# SCOND   ::= quoted_regex


log = logging.getLogger()

def tokenize_line(line):
	return tokenize.generate_tokens(StringIO(line).readline)


class ParseError(Exception):
	def __init__(self, t):
	    self.msg = ("Unexpected token: '" + t.string +
	                "' at position " + str(t.start[1]))


class Tokens:
	def __init__(self, line):
	    self.token_generator = tokenize_line(line)

	def peek(self):
	    val = self.token_generator.__next__()
	    self.token_generator = itertools.chain([val], self.token_generator)
	    return val

	def next(self):
	    return self.token_generator.__next__()

class Filter:
	def __init__(self, line, clauses):
		self.line = line
		self.clauses = clauses

	def __str__(self):
		return line

	def match(self, instr):
		return all([clause(instr) for clause in self.clauses])


def expect(tokens, type):
	if tokens.peek().type != type:
	    raise ParseError(tokens.peek())
	assert(tokens.peek().type == type)
	return tokens.next()


def exec_re(r, i):
	worked = r.search(i) is not None
	log.debug("Searching '{}' for regex '{}', got {}".format(i, r.pattern, worked))
	return worked


def parse_scond(tokens, d):
	log.debug(d + "parse_scond " + tokens.peek().string)
	val = expect(tokens, tokenize.STRING)
	terminal_regex = re.compile(val.string[1:-1])  # need to trim the quotes!
	return lambda input: exec_re(terminal_regex, input)


def parse_cond(tokens, d):
	log.debug(d + "parse_cond " + tokens.peek().string)
	l = parse_scond(tokens, d + "  ")
	if tokens.peek().string == "AND":
	    logging.debug(d + "AND")
	    tokens.next()  # throw it away!
	    r = parse_cond(tokens, d + "  ")
	    return lambda line: l(line) and r(line)
	else:
	    return l


def parse_clause(tokens, d):
	log.debug(d + "parse_clause " + tokens.peek().string)
	a_or_r = expect(tokens, tokenize.NAME)
	l = parse_cond(tokens, d + "  ")
	if a_or_r.string == "accept":
	    return l
	elif a_or_r.string == "reject":
	    return lambda line: not l(line)
	else:
	    raise ParseError(a_or_r)


def parse_clauses(tokens, d):
	log.debug(d + "parse_clauses " + tokens.peek().string)
	clauses = []
	while tokens.peek().type == tokenize.NAME:
	    clauses.append(parse_clause(tokens, d + "  "))

	return clauses


def parse_command(line):
	[name, rules] = line.split(": ", 1)
	tokens = Tokens(rules)
	clauses = parse_clauses(tokens, "")
	expect(tokens, tokenize.ENDMARKER)
	return (name, Filter(line, clauses))


def execute(fil, input):
	return all([clause(input) for clause in fil.clauses])
