def main(options, *args):
    try:
        pass
    except Exception, e:
        print e
        return -1
        
if __name__ == "__main__":
    from optparse import OptionParser, Option
    parser = OptionParser(usage='''\
    %prog [-m mod "args"]
''')
    parser.add_option(Option("-m", "--mod",
            action="append", type="string", dest="startup_mods", nargs=2,
            default=[], help="""\
-m mod-name "startup params". This option says which mods to load when the rig starts."""))
    try:
        (options, args) = parser.parse_args()
    except:
        print e
        sys.exit(-1)
    sys.exit(main(options, *args))
