#!/usr/bin/env python

# and example command line.
# -c LINE store -c SPEAKER store -c STAGEDIR store -c SPEECH store
#

try:
    from rig.modformat import STORE_FIELD_SEPERATOR, STORE_RECORD_SEPERATOR
except ImportError:
    print "please add the parent folder of your rig source tree to your PYTHONPATH"
    STORE_FIELD_SEPERATOR='<>'
    STORE_RECORD_SEPERATOR='\n'    

import sys, os, string
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from elementtree import ElementTree

trace_actions=True

class Error(Exception):
   pass

class O:
    def __init__(self, atts):
        self.__dict__.update(atts)
        
def ElementCan(**atts): 
    return O(atts)

class Compiler(ElementTree.TreeBuilder):
    '''Prepares mod data from asset sources.
    
    At present it processes the input file, pulls out the element tags and content 
    that are specified on the command line and generates sequence data. The 
    sequence data is heapq friendly form: (start, end). (tupples sort lexicaly)
    start and end are defined to work exactly like python 'slice' indices.
    
    The last step is to pack the sequence data, content and other generated meta
    data into MOD format. This isn't done yet. For now I'm working towards an 
    interim format that will get us going without tying our (will's ;-) hands. 
    see the end of this file for my very rough notes on where this interim format 
    is going at the moment.

    The output will written to the files 'as we go' this is so we don't make
    silly demands on memory while compiling large sources.

    The seqence data allows us to decompose tree structured data (XML) into sets of 
    flat tables. the sequence data preserves the order information we need for 
    playback. the 'flattening' allows us to rearange our data to meet load and 
    runtime access demands.
    
    This scheme comfortably handles element tags that appear at multiple 
    levels of the content heirarchy, consider <STAGEDIR> in:
    
        <SPEECH>
        <SPEAKER>MACBETH</SPEAKER>
        <LINE><STAGEDIR>Aside</STAGEDIR>  Glamis, and thane of Cawdor!</LINE>
        <LINE>The greatest is behind.</LINE>
        <STAGEDIR>To ROSS and ANGUS</STAGEDIR>
        <LINE>Thanks for your pains.</LINE>
        <STAGEDIR>To BANQUO</STAGEDIR>      # Note this is a child of SPEECH not LINE as above.
        <LINE>Do you not hope your children shall be kings,</LINE>
        <LINE>When those that gave the thane of Cawdor to me</LINE>
        <LINE>Promised no less to them?</LINE>
        </SPEECH>
    
    output: 
        inputfilebasename.index - indexes the content, including load hints like sequencing data.
        inputfilebasename.content - the content extracted from the sources and, potentialy, reformated.
        inputfilebasename.mod - manifest and overal 'MOD' properties
    '''
    
    def __init__(self, parser, options, element_factory=None):
        ElementTree.TreeBuilder.__init__(self, element_factory)
        
        self.parser = parser
        
        self.mapActionApplicationOrder = {
            'strip':1, 
            # strip has no sub actions.    
            'store':2, 
            'justboundary':5 # can combine with store
        }
        applicationOrder = [(v,k) for (k,v) in self.mapActionApplicationOrder.iteritems()]
        applicationOrder.sort()
        self.mapApplicationOrderAction={}
        for (v,k) in applicationOrder:
            self.mapApplicationOrderAction[v]=k
        del applicationOrder
    
    def store_element(self, elem, storewhere, storecontentwhere):
            
        sq, sqparent = elem.sq, elem.sqparent
        
        # KLUDGE: elements with no content come through with '\n'. Remove this.
        if elem.content == '\n':
            elem.content = ''
        if trace_actions: print "%s: store, %s with content:= %s" % (sq, elem.tag, elem.content)
        if trace_actions: print "element def -> %s, content -> %s" % (storewhere, storecontentwhere)
        
        assert storewhere != "index" and storecontentwhere != "index"
        
        elemfile = getattr(self, 'outfile_' + storewhere)
        contentfile = getattr(self, 'outfile_' + storecontentwhere)
    
        contentrepr = [elem.content]
        contentrepr = string.join(contentrepr, STORE_FIELD_SEPERATOR)
        if contentrepr: # KLUDGE: don't add the newline if we have no content.
            contentrepr += STORE_RECORD_SEPERATOR
        
        contentfstart = contentfile.tell()
        contentfstop = contentfstart + len(contentrepr) -1
        
        elemrepr = [elem.tag, str(len(elem.children))]
        elemrepr = string.join(elemrepr, STORE_FIELD_SEPERATOR) + STORE_RECORD_SEPERATOR

        if elemfile is contentfile:
            elemfstart = contentfstop + 1
            elemfstop = elemfstart + len(elemrepr) -1
        else:
            elemfstart = elemfile.tell()
            elemfstop = elemfstart + len(elemrepr) -1
        
        elemfile.write(elemrepr)
        if contentfstart != contentfstop:
            contentfile.write(contentrepr)
        
        indexentry = [sq, sqparent, 
            storewhere, elemfstart, elemfstop, 
            storecontentwhere, contentfstart, contentfstop]
                
        # keeping the entire index in memory for now ...
        self._channelElementIndex.setdefault(elem.tag,{})[sq[0]]=indexentry
        self._elementIndex[sq[0]]=indexentry
        
        # keeping the elements around in memory for now ...
        self._elements[sq[0]] = elem

        
        
    def beginfile(self, options, infilename, infile):
        self.compilemore_chunksize = 32768 # MAGIC
        self.infilename = os.path.abspath(infilename)
        self.infile = infile or file(self.infilename)
        self.modname = os.path.basename(
                    os.path.splitext(self.infilename)[0])
        self.outpath = os.path.normpath(
            os.path.join(options.mod_dir, self.modname))
        try:
            os.makedirs(self.outpath)
        except:
            pass
        self.outfilename_index = os.path.join(self.outpath, self.modname) + '.index' # MAGIC
        self.outfilename_meta = os.path.join(self.outpath, self.modname) + '.meta' # MAGIC
        self.outfilename_content = os.path.join(self.outpath, self.modname) + '.content' # MAGIC
        self.outfilename_mod = os.path.join(self.outpath, self.modname) + '.mod' # MAGIC
        
        self.outfile_index = file(self.outfilename_index, 'w')
        self.outfile_meta = file(self.outfilename_meta, 'w')
        self.outfile_content = file(self.outfilename_content, 'w')
        self.outfile_mod = file(self.outfilename_mod, 'w')
        
        self.channels = {}
        for (name, actions) in options.channel_actions:
            # tit about normalising the combination of actions.
            actionMethodName = [(self.mapActionApplicationOrder[action], action) 
                for action in string.split(string.lower(actions),'_')]
            actionMethodName.sort()
            actionMethodName = string.join([a for (o,a) in actionMethodName],'_')
            # if the normalised combination is not an attribute default to store_flatten
            # ie if a channel is named at all in the options there will be *something* 
            # in the output corresponding to that channel.
            self.channels[name] = getattr(self, actionMethodName, self.store)
        self._sequence=0
        self._sequenceStack=[]
        
        # for tracking where removals came from. not implemented yet 
        # as it only a 'MAY need' feature. A use case is mixing down from
        # multiple sources where there are assosiations between the sources
        # that need to be cross referenced when mixing. In particular 
        # Michela's example XML for the macbeth movie with the original
        # macbeth.xml.
        #
        # this would mean we would _need_ to be able to map where 
        # things were removed from in the space of the original spaces. 
        # Of course the spaces of the original sources would need to 
        # be homogenous, or transformable into a common space, for 
        # this to work.
        #
        # self.antiSequence=0
        # self.antiSequenceStack=[]
        
        self._elements={}
        self._elementIndex={}
        self._channelElementIndex={}
        
    def endfile(self):
        # write the master index.
        # [sq, sqparent, 
        #    storewhere, elemfstart, elemfstop, 
        #    storecontentwhere, contentfstart, contentfstop]
        # release the references to the files we just finished with.
        f = self.outfile_index
        f.write('<?xml version="1.0"?>\n')
        f.write('<channels><count>%d</count>\n' % len(self._channelElementIndex.keys()))
        
        for channel, channelindex in self._channelElementIndex.iteritems():
            f.write('<channel><name>%s</name><count>%d</count>\n' % (
                channel, len(channelindex.keys())))
            # sort the sequence.
            sequence = channelindex.keys()
            sequence.sort()
            sequence = map(channelindex.__getitem__, sequence)
            # now write it.
            for (sq, sqparent, metasource, metastart, metastop, 
                contentsource, contentstart, contentstop) in sequence:
                sqrepr = '''\
        <sq-item><id>%d</id><sq>%d %d</sq><sq-parent-id>%d</sq-parent-id>
        <source><name>%s</name><first>%d</first><last>%d</last></source>
        <source><name>%s</name><first>%d</first><last>%d</last></source>
        </sq-item>\n''' % (sq[0], sq[0], sq[1], sqparent, 
                metasource, metastart, metastop,
                contentsource, contentstart, contentstop)
                f.write(sqrepr)
            f.write('</channel>')
        f.write('</channels>')
        
        del self.infilename
        del self.outfilename_index
        del self.outfilename_content
        del self.outfilename_mod
        # AND make damned sure the data is pushed through any IO buffering.
        self.infile.flush(); self.infile.close(); del self.infile
        self.outfile_index.flush(); self.outfile_index.close(); del self.outfile_index
        self.outfile_content.flush(); self.outfile_content.close(); del self.outfile_content
        self.outfile_mod.flush(); self.outfile_mod.close(); del self.outfile_mod
        
    def compilemore(self):
        data = self.infile.read(self.compilemore_chunksize)
        self.parser.feed(data)
        return data

    def sequence_advance(self, start):
        '''Advance the sequence.
       
        And return priority queue friendly sequence code.
        
        Sequence start, end are compatible with python slicing rules 
        for indices. ie end is the point imediately before the first 
        element of the next sequenced thing.
        
        When called from 'end' the sequence code is the 'slice' of the 
        element and all it's sequenced children.
        
        When called from 'start' the sequence code 'end' field is None.
        '''
        
        if start:
            sequence = self._sequence
            self._sequence += 1
            self._sequenceStack.append(sequence)
            return (sequence, None)
        else:
            sequence = self._sequenceStack.pop()
            sequenceEnd = self._sequence
            return (sequence, sequenceEnd)
            
    def sequence(self, start):
        '''Return the current sequence tuple.
        
        This is the sequence of the _previous_ element at the same depth 
        as the element being parsed.
        
        It is safe to do:
            
            # gets the current sequence at the current elements stack level
            # without poping the stack.
            sq = sequence()
            
            # do some stuff, including manipulation of the sequence.
            
            # Then if appropriate
            sq = sequence_advance() 
            
        if there is no intervening manipulation of sequencing 
        then this identity holds:
            sequence()[0]+1 == sequence_advance()[0]
        '''
        if start:
            return (self._sequence-1, None)
        else:
            return (self._sequenceStack[-1]-1, self._sequence-1)
        
    # element 'action' methods. attrs is always none if start is False
    def strip(self, elem, start=False, attrs=None):
        # do NOT update sequence for things we strip out.
        # sq = self.sequence_advance(start)
        
        # we would instead do: antisq = self.anti_sequence(start)
        # if we wanted to track where removals were.
        
        if not start: 
            if trace_actions: print "%s: strip, %s with content:= %s" % ("DEL", elem.tag, elem.text)
            elem.clear()
            
    def store(self, elem, start=False, attrs=None):
        sq = self.sequence_advance(start)
        if not start:
            if len(self._sequenceStack):
                sqparent = self._sequenceStack[-1]
            else:
                sqparent = -1
            self.store_element(ElementCan(
                sq=sq, sqparent=sqparent, tag=elem.tag, content=elem.text, 
                children=[i for i in xrange(*sq)]), "meta", "content")
            elem.clear()
                
    def store_justboundary(self, elem, start=False, attrs=None):
        sq = self.sequence_advance(start)
        if not start: 
            if trace_actions: print "%s: store_justboundary, %s with content:= %s" % (sq, elem.tag, elem.text)
            elem.clear()
    
    def start(self, tag, attrs):
        elem = ElementTree.TreeBuilder.start(self, tag, attrs)
        self.channels.get(elem.tag, self.strip)(elem, True, attrs)
    def end(self, tag):
        elem = ElementTree.TreeBuilder.end(self, tag)
        self.channels.get(elem.tag, self.strip)(elem)

test_data_short = """\
<ACT><TITLE>ACT I</TITLE>

<SCENE><TITLE>SCENE I.  A desert place.</TITLE>
<STAGEDIR>Thunder and lightning. Enter three Witches</STAGEDIR>

<SPEECH>
<SPEAKER>First Witch</SPEAKER>
<LINE>When shall we three meet again</LINE>
<LINE>In thunder, lightning, or in rain?</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>Second Witch</SPEAKER>
<LINE>When the hurlyburly's done,</LINE>
<LINE>When the battle's lost and won.</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>Third Witch</SPEAKER>
<LINE>That will be ere the set of sun.</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>First Witch</SPEAKER>
<LINE>Where the place?</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>Second Witch</SPEAKER>
<LINE>Upon the heath.</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>Third Witch</SPEAKER>
<LINE>There to meet with Macbeth.</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>First Witch</SPEAKER>
<LINE>I come, Graymalkin!</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>Second Witch</SPEAKER>
<LINE>Paddock calls.</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>Third Witch</SPEAKER>
<LINE>Anon.</LINE>
</SPEECH>

<SPEECH>
<SPEAKER>ALL</SPEAKER>
<LINE>Fair is foul, and foul is fair:</LINE>
<LINE>Hover through the fog and filthy air.</LINE>
</SPEECH>

<STAGEDIR>Exeunt</STAGEDIR>
</SCENE>
</ACT>
"""

def main(options, *args):
    try:
        parser = ElementTree.XMLTreeBuilder()
        compiler = parser._target = Compiler(parser, options) # plug in a custom builder
        try:
            if args and os.path.isfile(args[0]):
                compiler.beginfile(options, args[0], file(os.path.abspath(args[0])))
                while compiler.compilemore():
                    pass
            else:
                compiler.beginfile(options, 'test_data_short.xml',  StringIO(test_data_short))
                while compiler.compilemore():
                    pass
        finally:
            compiler.endfile()
        
        if 0:
            sequence = parser._target._elements.keys()
            sequence.sort()
            for q in sequence:
                e = parser._target._elements[q]
                if e.content and e.content != '\n':
                    print "{%s,%s} %s\n" % (e.sq, e.tag, e.content)
                else:
                    print "{%s,%s}\n" % (e.sq, e.tag)
    
    except Exception, e:
        print e
        return -1
        
if __name__ == "__main__":
    from optparse import OptionParser, OptionGroup, Option

    parser = OptionParser(usage='''\
    %prog [(-c channel-name action)* (--d path) | -h] source.xml)

All channel options operate on a stream of 'like' elements. Normalised 
names and for all items in an extracted channel are generated. All items 
for all channels are numbered. The 'number space' for all items is global 
to the mod. 
''')
    parser.add_option(Option("-c", "--channel",
            action="append", type="string", dest="channel_actions", nargs=2,
            default=[], help="""\
-c channel-name action-to-take. This option controls compilation of a specific 
xml tag stream."""))
    parser.add_option(Option("-d", "--mod-dir", action="store", type="string", dest="mod_dir", 
            default="../mods/", help='''mod directory.'''))
    
    try:
        (options, args) = parser.parse_args()
    except:
        print e
        sys.exit(-1)
    sys.exit(main(options, *args))

'''
Test FORMAT Notes
-----------------

this description is (intended to be) neutral with regards text/binary representation.

manifest

    tbd: plugin interface binding data.
    index file name.
    content file name.
    
index

    symbol table.
    
    element_sequencing
        element_sequences size count num_sequences
            sequence_id size count sequence
            sequence[num_sequences]

general container element format

this is a packing format and so needs to makes as few assumptions about the 
concrete data types as possible. the format aims to transcribe the information 
nescessary to arrange for efficient loading.

TYPE_DECORATOR, INSTANCE_ID, SIZE, COUNT, ISTANCE_META_DATA[SIZE]

The requirement to have the size up and count, up, front releives the burden on 
the heap during loading as well as making things generaly more convenient to work 
with. Not all 'things' are of fixed side. so size(array)/sizeof(thing) is not 
allways possible. for this reason count is included.

for xml conformance we probably need a general container for our elements that 
specifies the above rules. ie a 'thing' is always: 
    thing { type_decorator, instance_id, size, count, instance_data }
    
symbols, id, size, count, { 

a map of all xxx_id's to their symbolic identifiers

Allows external things to reference into the mod using names, including the runtime,
On disc, within the scope of this unit, all references are by the numbers 
defined in this table. There is nothing in this format that says anything about
what names should be. unicode _must_ be supported in the final form. 

    num_symbols
    (id, identifier)[num_symbols] for all id's that have names.
    num_anon_symbols
    (id, identifier)[num_anon_symbols] for all id's that are anonymous.
}

element_can, element_can_id, size, { 

a canister for a single element

    tag, - the original source clasifier for this element.
    desc, - the original source identifier for this element. ("" means anon)
    content_ref_id, - indirection to a content locator
    num_children, - how many child elements does this can have ?
    child_id[num_children] - child element_can_id's
    }
    
element_sequence, element_sequence_id, size { 

a canister for a set of element sequence data.

    sequence_length,
    (order, element_can_id)[sequence_length]
    }
    
content_can, content_can_id, size, { 

a canister for some content. content_ref_id's refer _into_ a particular content_can.

    source_ref_id,
    data_size,
    data[size]
    }

content_ref, content_ref_id, size { 

a reference to a peice of content

    type_meta_data_id,
    content_can_id - from which can ?
    start, end - what range ? python 'slice' compatible scheme.
    
source_ref, source_ref_id, size {
    url - from which file ?
    start, end, - what range ? python 'slice' compatible scheme.
    }
    
referencing is used to connect elements. We could allow for by value 
duplication to allow data chunks to be compiled with better locality of 
reference. Not going to do this for now.
'''
