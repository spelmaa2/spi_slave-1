import os
import sys
if not (os.path.abspath('../../thesdk') in sys.path):
    sys.path.append(os.path.abspath('../../thesdk'))

import numpy as np
import tempfile

from thesdk import *
from verilog import *
from verilog.testbench import *
from verilog.testbench import testbench as vtb
from vhdl import *

class inverter(vhdl,verilog,thesdk):
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,*arg): 
        self.print_log(type='I', msg='Inititalizing %s' %(__name__)) 
        self.proplist = [ 'Rs' ];    # Properties that can be propagated from parent
        self.Rs =  100e6;            # Sampling frequency
        self.IOS=Bundle()
        self.IOS.Members['A']=IO(dir='in', iotype='sample', ionames=['A']) # Pointer for input data
        self.IOS.Members['Z']= IO(dir='out', iotype='sample', ionames=['Z'], datatype='int')
            # Pointer for output data
        self.model='py';             # Can be set externally, but is not propagated
        self.par= False              # By default, no parallel processing
        self.queue= []               # By default, no parallel processing
        self.IOS.Members['control_write']= IO(
                name='control_write', 
                dir='in',
                iotype='file',
                Data=Bundle() 
                )        #Bundle of control input files

        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;

        self.init()

    def init(self):
        if self.model=='sv':
            # Adds an entry named self.iofile_Bundle.Members['A']
            # For inputs this is automated
            for ioname, val in self.IOS.Members.items():
                print(val.dir)
                if val.dir is 'in' and val.iotype is not 'file':
                    _=verilog_iofile(self,name='A',dir='in')
                elif val.dir is 'out' and val.iotype is not 'file': 
                    if val.datatype is not None:
                        _=verilog_iofile(self,name=ioname,datatype=val.datatype) #int or complex 
                    else:
                        # Output file reader do not know if they are complex or not.
                        # This could be automated if there would be a way to determine the output
                        # datatype fom the assingmnet target
                        self.print_log(type='F', 
                                msg='Attribute \'datatype\' not defined for output %s.\n Mandatory values for ouput IO associated with verilogfile are \'int\' | \'sint\' | \'complex\' | \'scomplex\'.' %(ioname)
                            )

            #_=verilog_iofile(self,name='Z',datatype='int') #int or complex 
            self.vlogparameters=dict([ ('g_Rs',self.Rs),])

        ### Lets fix this later on
        if self.model=='vhdl':
            a=vhdl_iofile(self,name='A')
            a.simparam='-g g_outfile='+a.file
            b=vhdl_iofile(self,name='Z')
            b.simparam='-g g_infile='+b.file
            self.vhdlparameters =dict([('g_Rs',self.Rs)])

    def main(self):
        out=np.array(1-self.IOS.Members['A'].Data)
        if self.par:
            self.queue.put(out)
        self.IOS.Members['Z'].Data=out

    def run(self,*arg):
        if len(arg)>0:
            self.par=True      #flag for parallel processing
            self.queue=arg[0]  #multiprocessing.queue as the first argument
        if self.model=='py':
            self.main()
        else: 
          if self.model=='sv':
              # Adoption transfers parenthood of the files to this instance
              self.IOS.Members['control_write'].Data.Members['control_write'].adopt(parent=self)
              # Create testbench and execute the simulation
              self.define_testbench()
              self.connect_inputs()
              self.format_ios()
              self.tb.generate_contents()
              self.tb.export(force=True)
              self.write_infile()
              self.run_verilog()
              self.read_outfile()
              
              #There should be a method for this
              self.IOS.Members['Z'].Data=self.iofile_bundle.Members['Z'].Data
              
              #This is for parallel processing
              if self.par:
                  self.queue.put(self.IOS.Members[Z].Data)
              del self.iofile_bundle #Large files should be deleted

          elif self.model=='vhdl':
              self.run_vhdl()
              self.read_outfile()

    # Automate this bsed in dir
    def connect_inputs(self):
        # Create TB connectors from the control file
        # See controller.py
        for ioname,val in self.IOS.Members.items():
            if val.iotype is not 'file' and val.dir is 'in': 
                # Data must be properly shaped
                self.iofile_bundle.Members[ioname].Data=self.IOS.Members[ioname].Data
            elif val.iotype is 'file': #If the type is file, the Data is a bundle
                for bname,bval in val.Data.Members.items():
                    for connector in bval.verilog_connectors:
                        self.tb.connectors.Members[connector.name]=connector
                        # Connect them to DUT
                        try: 
                            self.dut.ios.Members[connector.name].connect=connector
                        except:
                            pass

        # IO file connector definitions
        # Define what signals and in which order and format are read form the files
        # i.e. verilog_connectors of the file
        # Every IO file should ha
        name='Z'      # Name of the file
        ionames=[]    # List of verilog signals handled by tha file
        ionames+=['Z']
        self.iofile_bundle.Members[name].verilog_connectors=\
                self.tb.connectors.list(names=ionames)

        # Write outputs only if reset phase is done 
        # cond string appended to validity requirement of the io
        # See controller.py
        self.iofile_bundle.Members[name].verilog_io_condition_append(cond='&& initdone')

        name='A'
        ionames=[]
        ionames+=['A']
        self.iofile_bundle.Members[name].verilog_connectors=\
                self.tb.connectors.list(names=ionames)
        self.iofile_bundle.Members[name].verilog_io_condition='initdone'

    # Define if the signals are signed or not
    # Can these be deducted?
    def format_ios(self):
        # Verilog module does not contain information if the bus is signed or not
        # Prior to writing output file, the type of the connecting wire defines
        # how the bus values are interpreted. 
        for ioname,val in self.IOS.Members.items():
            if ioname in self.iofile_bundle.Members and val.dir is 'out':
                if (val.datatype is 'sint' ) or (val.datatype is 'scomplex'):
                    for assname in val.ionames:
                        self.tb.connectors.Members[assname].type='signed'

    def define_testbench(self):
        #Initialize testbench
        self.tb=vtb(self)
        # Dut is creted automaticaly, if verilog file for it exists
        self.tb.connectors.update(bundle=self.tb.dut_instance.io_signals.Members)
        #Assign verilog simulation parameters to testbench
        self.tb.parameters=self.vlogparameters
        

        # Copy iofile simulation parameters to testbench
        for name, val in self.iofile_bundle.Members.items():
            self.tb.parameters.Members.update(val.vlogparam)

        # Define the iofiles of the testbench. '
        # Needed for creating file io routines 
        self.tb.iofiles=self.iofile_bundle

        #Define testbench verilog file
        self.tb.file=self.vlogtbsrc
        
        # Create clock if nonexistent 
        if 'clock' not in self.tb.dut_instance.ios.Members:
            self.tb.connectors.Members['clock']=verilog_connector(
                    name='clock',cls='reg', init='\'b0')

        # Create reset if nonexistent 
        if 'reset' not in self.tb.dut_instance.ios.Members:
            self.tb.connectors.Members['reset']=verilog_connector(
                    name='reset',cls='reg', init='\'b0')

        ## Start initializations
        #Init the signals connected to the dut input to zero
        for name, val in self.tb.dut_instance.ios.Members.items():
            if val.cls=='input':
                val.connect.init='\'b0'

if __name__=="__main__":
    import matplotlib.pyplot as plt
    from  inverter import *
    from  inverter.controller import controller as inverter_controller
    import pdb
    length=1024
    rs=100e6
    indata=np.random.randint(2,size=length).reshape(-1,1);
    controller=inverter_controller()
    controller.Rs=rs
    #controller.reset()
    #controller.step_time()
    controller.start_datafeed()

    duts=[inverter() for i in range(2) ]
    duts[0].model='py'
    duts[1].model='sv'
    for d in duts: 
        d.Rs=rs
        #d.interactive_verilog=True
        d.IOS.Members['A'].Data=indata
        d.IOS.Members['control_write']=controller.IOS.Members['control_write']
        d.init()
        d.run()

    # Obs the latencies may be different
    latency=[ 0 , 1 ]
    for k in range(len(duts)):
        figure=plt.figure()
        h=plt.subplot();
        hfont = {'fontname':'Sans'}
        x = np.linspace(0,10,11).reshape(-1,1)
        markerline, stemlines, baseline = plt.stem(\
                x,indata[0:11,0],'-.'
            )
        markerline, stemlines, baseline = plt.stem(\
                x, duts[k].IOS.Members['Z'].Data[0+latency[k]:11+latency[k],0], '-.'
            )
        plt.setp(markerline,'markerfacecolor', 'b','linewidth',2)
        plt.setp(stemlines, 'linestyle','solid','color','b', 'linewidth', 2)
        plt.ylim(0, 1.1);
        plt.xlim((np.amin(x), np.amax(x)));
        str = "Inverter model %s" %(duts[k].model) 
        plt.suptitle(str,fontsize=20);
        plt.ylabel('Out', **hfont,fontsize=18);
        plt.xlabel('Sample (n)', **hfont,fontsize=18);
        h.tick_params(labelsize=14)
        plt.grid(True);
        printstr="./inv_%s.eps" %(duts[k].model)
        plt.show(block=False);
        figure.savefig(printstr, format='eps', dpi=300);
    input()
