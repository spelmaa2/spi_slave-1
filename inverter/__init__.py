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
        self.proplist = [ 'Rs' ];    # Properties that can be propagated from parent
        self.Rs =  100e6;            # Sampling frequency
        self.A = IO(dir='in', iotype='sample'); # Pointer for input data
        self.model='py';             # Can be set externally, but is not propagated
        self.par= False              # By default, no parallel processing
        self.queue= []               # By default, no parallel processing
        self.Z = IO(dir='out', iotype='sample'); # Pointer for input data
        self.control_write = IO(dir='in', iotype='event'); # Pointer for input data
        self.control_write.Data = Bundle() # This is actually a bundle of files
        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;


        self.init()

    def init(self):
        if self.model=='sv':
            # Adds an entry named self.iofile_Bundle.Members['A']
            _=verilog_iofile(self,name='A',dir='in')
             # Output file reader do not know if they are complex or not.
            _=verilog_iofile(self,name='Z',datatype='int') #int or complex 
            self.vlogparameters=dict([ ('g_Rs',self.Rs),])

        ### Lets fix this later on
        if self.model=='vhdl':
            a=vhdl_iofile(self,name='A')
            a.simparam='-g g_outfile='+a.file
            b=vhdl_iofile(self,name='Z')
            b.simparam='-g g_infile='+b.file
            self.vhdlparameters =dict([('g_Rs',self.Rs)])

    def main(self):
        out=np.array(1-self.A.Data)
        if self.par:
            self.queue.put(out)
        self.Z.Data=out

    def run(self,*arg):
        if len(arg)>0:
            self.par=True      #flag for parallel processing
            self.queue=arg[0]  #multiprocessing.queue as the first argument
        if self.model=='py':
            self.main()
        else: 
          if self.model=='sv':
              self.control_write.Data.Members['control_write'].adopt(parent=self)
              # Create testbench and execute the simulation
              self.define_testbench()
              self.tb.export(force=True)
              self.connect_ios()
              self.write_infile()
              self.run_verilog()
              self.read_outfile()
              
              #There should be a method for this
              self.Z.Data=self.iofile_bundle.Members['Z'].Data
              
              #This is for parallel processing
              if self.par:
                  self.queue.put(self.Z.Data)
              del self.iofile_bundle #Large files should be deleted

          elif self.model=='vhdl':
              self.run_vhdl()
              self.read_outfile()

    def connect_ios(self):
        self.iofile_bundle.Members['A'].Data=self.A.Data.reshape(-1,1)

    def format_ios(self):
        pass

    def write_infile(self):
        for name, val in self.iofile_bundle.Members.items():
            if val.dir=='in':
                self.iofile_bundle.Members[name].write()

    def read_outfile(self):
        for name, val in self.iofile_bundle.Members.items():
            if val.dir=='out':
                 self.iofile_bundle.Members[name].read()

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
        
        # Create TB connectors from the control file
        # See controller.py
        for connector in self.control_write.Data.Members['control_write'].verilog_connectors:
            self.tb.connectors.Members[connector.name]=connector
            # Connect them to DUT
            try: 
                self.dut.ios.Members[connector.name].connect=connector
            except:
                pass

        # Create clock as inverter does not have it 
        if 'clock' not in self.tb.dut_instance.ios.Members:
            self.tb.connectors.Members['clock']=verilog_connector(
                    name='clock',cls='reg', init='\'b0')

        ## Start initializations
        #Init the signals connected to the dut input to zero
        for name, val in self.tb.dut_instance.ios.Members.items():
            if val.cls=='input':
                val.connect.init='\'b0'

        # IO file connector definitions
        # Define what signals and in which order and format are read form the files
        # i.e. verilog_connectors of the file
        # Every IO file should ha
        name='Z' #Name of the file
        ionames=[]    # List of verilog signals handled by tha file
        ionames+=['Z']
        self.iofile_bundle.Members[name].verilog_connectors=\
                self.tb.connectors.list(names=ionames)

        # Set the testbench connector type to signed if needed
        for name in ionames:
            self.tb.connectors.Members[name].type='signed'

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

        self.tb.generate_contents()

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
        d.A.Data=indata
        d.control_write=controller.control_write
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
                x, duts[k].Z.Data[0+latency[k]:11+latency[k],0], '-.'
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
