from __future__ import print_function

from io import open
# ^^ works with encoding param in Py 2
import os
import re
import json
import tvdb_api
import colorama
import shutil, errno
from subprocess import call as call
from sys import argv
from sys import exit as sysexit
from sys import version_info
from platform import system

from tvdb_api import tvdb_error
from tvdb_api import tvdb_shownotfound
from tvdb_api import tvdb_seasonnotfound

# Version Compat
if version_info < (3,0):
	input = raw_input
else:
	unicode = str

colorama.init(autoreset=True)

namingFormat = ''
configs = ''
ENC = 'utf-8'
VERSION = '1.1.2'
epns = {}
renames = {}


def createConfig(fpath):
	'''
	Creates the config file if needed
	'''
	if not os.path.isfile(fpath):
		x = {
			"namingFormat": "{{sname}} [{{seasonnumber}}x{{episodenumber}}] - {{episodename}}",
			"_commented_namingFormat": "{{sname}} E{{absolute_number}} - {{episodename}}",
			"replaces": {
				"&": "-",
				"YouTube_": "~"
			}
		}
		ptr = open(fpath, 'w')
		ptr.write(unicode(json.dumps(x, indent=4)))
		ptr.close()


def loadConfig():
	"""
	Loads Configuration data from the config.json file
	"""
	global namingFormat, configs
	fpath = os.path.dirname(os.path.realpath(__file__)) + '/config.json'
	createConfig(fpath)
	with open(fpath) as data:
		configs = json.load(data)
	namingFormat = configs['namingFormat']


def editConfig():
	"""
	Opens the config in default editor
	"""
	fpath = os.path.dirname(os.path.realpath(__file__)) + '/config.json'
	createConfig(fpath)
	if system() == 'darwin':
		call(('open', fpath))
	elif os.name == 'nt':
		os.startfile(fpath)
	elif os.name == 'posix':
		call(('xdg-open', fpath))


def showHelp():
	'''
	Shows the help
	'''
	printexit(
		(
		"\n"
		"Series Renamer helps you properly name you tv/anime series episodes. Just start this application in the folder of your TV series and you are ready to go.\n"
		"\n"
		"Optional Arguments\n"
		"\n"
		"--config:         Edit config.json (linux users may need to add sudo)\n"
		"-H or --help:     Show help\n"
		"-V or --version:  Show version information"
		)
	)


def run():
	"""
	Runs the script from the setuptools entry point
	"""
	if len( argv ) > 1:
		if argv[1] == '--config':
			editConfig()
		elif argv[1] == '-H' or argv[1] == '--help':
			showHelp()
		elif argv[1] == '-V' or argv[1] == '--version':
			printexit(VERSION)
		else:
			print(colorama.Fore.RED + 'Incorrect arguments\n')
			showHelp()
	else:
		main( os.getcwd() )


def main(path='.'):
	"""
	Series Renamer commandline program
	"""

	loadConfig()
	print(colorama.Fore.MAGENTA + colorama.Style.BRIGHT + "What's the series name? Write it as precise as possible:")
	sname = input(colorama.Fore.CYAN + colorama.Style.BRIGHT + '> ')
	getNums(path)
	print(colorama.Fore.MAGENTA + "Fetching Series data from TheTVDB.com")
	seriesObj = getSeries(sname)
	printShowInfo(seriesObj)

	ps = '0'
	pep = 1
	allgo = done = dont = stop = 0

	strLog = ''

	for i in epns.items():
		dont = done = 0
		# season
		if ps[0] == '#':
			mys = int(ps[1:])
		elif len(i[1]) > 1:
			mys = i[1][int(ps)] if int(ps)>=0 else 0
		else:
			mys = 0
		# episode
		if len(i[1]) > 1:
			myep = i[1][pep]
		else:
			myep= i[1][0]

		while done == 0:
			print()
			print(colorama.Fore.MAGENTA + "Local file name: " + colorama.Style.DIM + trimUnicode(i[0]) )
			print(colorama.Fore.MAGENTA + "Detected order : " + colorama.Style.DIM + "[Season " + str(mys) + ", Episode " + str(myep) + "]")
			done = 1
			if allgo == 0:
				print(colorama.Fore.MAGENTA  + 'Array          :', colorama.Fore.MAGENTA + colorama.Style.DIM + str(i[1]))
				print(colorama.Fore.MAGENTA  + colorama.Style.BRIGHT + "Rename it? Choose one option: "
				    + colorama.Fore.GREEN    + "Yes(y) "
					+ colorama.Fore.RED      + "No(n) "
					+ colorama.Fore.BLUE     + "All(a) "
					+ colorama.Fore.YELLOW   + "Stop(s) "
					+ colorama.Fore.CYAN     + "Season_change(1) "
					+ colorama.Fore.WHITE    + "Episode_change(2) ")
				x = input(colorama.Fore.CYAN + colorama.Style.BRIGHT + '> ').lower()
				if x == 'y':
					continue
				elif x == 'n':
					dont = 1
				elif x == 'a':
					allgo = 1
				elif x == 's':
					dont = stop = 1
					break
				elif x == '1':
					print(colorama.Fore.MAGENTA + 'New season (-1, 0-{0}, #NUM) : '.format(len(i[1])-1), end='')
					ps = input(colorama.Fore.CYAN + colorama.Style.BRIGHT + '>> ')
					if ps[0] == '#':
						mys = int(ps[1:])
					elif int(ps) < 0:
						mys = 0
					elif int(ps) < len(i[1]):
						mys = i[1][int(ps)]
					done = 0
				elif x == '2':
					print(colorama.Fore.MAGENTA + 'New episode (0-{0}) : '.format(len(i[1])-1), end='')
					pep = int(input(colorama.Fore.CYAN + colorama.Style.BRIGHT + '>> '))
					if pep < len(i[1]) and pep >= 0:
						myep = i[1][pep]
					done = 0
				else:
					print(colorama.Fore.YELLOW + colorama.Style.BRIGHT + 'Invalid option. Try Again')
					done = 0

		if dont == 0: # if not not do it
			ext = getExtension(i[0])
			r_myep = str2Int(myep)
			if mys == 0:
				epd = seriesObj.search(r_myep, key='absolute_number')
				for epds in epd:
					if epds['absolute_number'] == str(r_myep):
						epd = epds
						break
				else:
					warn(colorama.Fore.YELLOW + 'Episode not found via absolute_number, skipping')
					continue

				mys = str(epd['seasonnumber'])
				epd['absolute_number'] = myep.replace(' ','')
			else:
				try:
					epd = seriesObj[ int(mys) ][r_myep]
					epd['episodenumber'] = myep.replace(' ','')
				except tvdb_seasonnotfound as e:
					warn(colorama.Fore.YELLOW +  'Season not found : ' + '{}'.format(e.args[-1]) )
					continue
				except tvdb_api.tvdb_episodenotfound as e:
					warn(colorama.Fore.YELLOW +  'Episode not found : ' + '{}'.format(e.args[-1]) )
					continue

			# check namingformat agains all available attributes
			tempmissing = isNameInvalid(epd)
			if tempmissing:
				warn(colorama.Fore.YELLOW + 'Naming Format ( ' + namingFormat + ' ) is invalid for tvdb data. Reason : missing ' + tempmissing)
			else:
				newname = makeName(sname, epd) + '.' + ext
				renames[i[0]] = newname
				strLog += '<tr><td>' + i[0] + '</td><td>' + newname + '</td></tr>'

		if stop:
			break

	if stop:
		return 1

	logfile = path + '/series_renamer_log.html'
	copyanything( os.path.dirname(os.path.realpath(__file__)) + '/logs.html', logfile )
	fpt = open(logfile, 'r', encoding=ENC)
	html = fpt.read()
	fpt.close()

	html = html.replace('{{dir}}', os.getcwd(), 1)
	html = html.replace('{{content}}', strLog, 1)
	fpt = open(logfile, 'w', encoding=ENC)
	fpt.write(unicode(html))
	fpt.close()

	print(colorama.Fore.MAGENTA + "Log created at: " + colorama.Style.DIM + logfile)
	print(colorama.Fore.MAGENTA + colorama.Style.BRIGHT
	    + "Do you approve renaming? "
		+ colorama.Fore.GREEN    + "Yes(y) "
		+ colorama.Fore.RED      + "No(n)")
	x = input(colorama.Fore.CYAN + colorama.Style.BRIGHT + '> ').lower()

	if x == 'y':
		for i in renames.items():
			if os.path.isfile(path + '/' + i[1]):
				warn(colorama.Fore.YELLOW + 'File {0} exists, skipping'.format(i[1]))
			else:
				os.rename(path + '/' + i[0], path + '/' + i[1])
				subtitleRename(path + '/' + i[0], path + '/' + i[1])
		print(colorama.Fore.GREEN + colorama.Style.BRIGHT + 'Renaming Successful! Goodbye :)')

	os.remove(logfile)
	return 0


def getNums(path):
	"""
	Scans the path, looks for series files and gets contenders of the episode numbers and season numbers.
	Stores them in epns
	"""

	exts = ['mkv', 'mp4', 'avi', 'flv', 'mpg', 'mpeg', 'wmv', 'webm', 'vob', 'mov', '3gp', 'ogv']

	for i in os.listdir(path):
		if not os.path.isfile(path + '/' + i):
			continue
		fname = i
		ext = getExtension(fname).lower()
		for k in configs['replaces'].items():
			fname = fname.replace(k[0], k[1])
		if ext in exts:
			tobj = re.findall("(?i)((^|.)\d+(\s*\-\s*\d+)?)(?=[\. ex\-\]\)\(\[$_])", fname, re.DOTALL) # because of 2 () 2 capturing groups
			# (?=[\. ex\-\]\)\(\[$])
			if len(tobj):
				epns[i] = tobj


	# check using prefix to nums
	# currently found none, everything is plausible
	avoids = ['~']
	for i in epns.items():
		nl = []
		for k in i[1]:
			temp = k[0][0] # so using double reference
			if temp in avoids:
				continue
			nl.append( re.findall("([1-9]\d*(\s*\-\s*[1-9]\d*)?)", k[0])[0][0] )
		epns[i[0]] = nl

	return


def getSeries(sname):
	"""
	Gets Series data using the TVDB API
	Throws exception if something goes wrong
	"""

	x = 0
	try:
		t = tvdb_api.Tvdb()
		x = t[sname]
	except tvdb_error:
		throwError(colorama.Fore.RED + colorama.Style.BRIGHT + "There was an error connecting the TVDB API")
	except tvdb_shownotfound:
		throwError(colorama.Fore.RED + colorama.Style.BRIGHT + "Show Not Found on TVDB")
	except Exception:
		throwError(colorama.Fore.RED + colorama.Style.BRIGHT + "There was an error. Tvdb API")
	return x


def makeName(sname, eobj):
	"""
	Makes the episode name using the namingFormat
	sname = Name of the series
	eobj = Episode Object containing all other data
	"""

	s = namingFormat
	o = re.findall('\{\{.+?\}\}', s)
	for i in o:
		if i == '{{sname}}':
			s = s.replace(i, fixName(sname), 1)
		else:
			s = s.replace(i, fixName(eobj[ i[2:-2] ]), 1)
	return s


def isNameInvalid(epd):
	"""
	Checks the namingFormat against the episode data to see if every request attribute is present
	"""
	o = re.findall('\{\{(.+?)\}\}', namingFormat)
	for i in o:
		if i == 'sname':
			continue
		if i not in epd:
			return i
		if epd[i] is None:
			return i
	return 0


def fixName(s):
	"""
	Removes parts in the string that can't be part of a filename.
	Eg - : in Windows
	"""
	windows = '/\\:*?"<>|'

	if system() == 'Windows':
		for i in windows:
			s = s.replace(i,'')

	return s


# More Functions

def printShowInfo(obj):
	'''
	Displays basic show info on the terminal
	'''
	drawline('-', '#'*80)
	print(colorama.Fore.MAGENTA + 'Series name       : ', colorama.Fore.MAGENTA + colorama.Style.DIM + obj['seriesname'])
	print(colorama.Fore.MAGENTA + 'Overview          : ', colorama.Fore.MAGENTA + colorama.Style.DIM + obj['overview'])
	c = -1
	try:
		obj[0]
	except tvdb_api.tvdb_seasonnotfound:
		c = 0
	print(colorama.Fore.MAGENTA + 'Number of seasons : ', colorama.Fore.MAGENTA + colorama.Style.DIM + str(len(obj)+c))
	drawline('-', '#'*80)


def getExtension(fname):
	"""
	Gets extension from the file name.
	Returns without the dot (.)
	"""
	a = fname.rfind('.')
	return fname[a+1:]


def subtitleRename(old, new):
	'''
	Renames subtitles a/c the file rename
	'''
	namebase = old[:old.rfind('.')]
	newnamebase = new[:new.rfind('.')]
	sub_formats = ['srt', 'sub', 'sbv', 'ttxt', 'usf', 'smi'] # https://en.wikipedia.org/wiki/Subtitle_(captioning)#Subtitle_formats
	for ext in sub_formats:
		if os.path.isfile(namebase + '.' + ext):
			print(colorama.Fore.MAGENTA + 'Subtitle found, renaming..')
			os.rename(namebase + '.' + ext, newnamebase + '.' + ext)


def trimUnicode(s):
	"""
	Trims string s of unicode text
	"""
	return re.sub(r'[^\x00-\x7F]+',' ', s)


def copyanything(src, dst):
	"""
	copy tree from src to dst
	Taken from Stack Overflow (dont have the link)
	"""
	try:
		shutil.copytree(src, dst)
	except OSError as exc: # python >2.5
		if exc.errno == errno.ENOTDIR:
			shutil.copy(src, dst)
		else: raise
	return


def str2Int(num):
	"""
	Converts string to int
	If form of 324-325, it returns 324 i.e. the former number
	"""
	n = re.findall('[1-9]\d*', str(num))
	return int(n[0])


def drawline(char, msg):
	"""
	Draws a line in the terminal
	"""
	print(colorama.Fore.MAGENTA + colorama.Style.DIM + char * (len(msg)+10))


def warn(msg):
	"""
	Gives a warning
	"""
	drawline(colorama.Fore.YELLOW + '>', msg)
	print(colorama.Fore.YELLOW + colorama.Style.BRIGHT + "WARNING :",
	    colorama.Fore.YELLOW + msg)
	drawline(colorama.Fore.YELLOW + '>', msg)


def throwError(msg):
	"""
	Throws error and exists
	"""
	drawline(colorama.Fore.RED + '#', msg)
	print(colorama.Fore.RED + colorama.Style.BRIGHT + "ERROR :",
	    colorama.Fore.RED + msg)
	sysexit()


def printexit(msg, code=0):
	'''
	Prints and exists
	'''
	print(colorama.Fore.MAGENTA + msg)
	sysexit(code)


# Main

if __name__ == "__main__":
	if len(argv) > 1:
		if argv[1] == '--config':
			editConfig()
	else:
		main()
