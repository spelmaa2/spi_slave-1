import os
import sys
if not (os.path.abspath('../../thesdk') in sys.path):
    sys.path.append(os.path.abspath('../../thesdk'))

import numpy as np

from thesdk import *
from vhdl import *
from vhdl.testbench import *
from vhdl.entity import *
from vhdl.testbench import testbench as vtb

class spi_slave(vhdl,verilog,thesdk):
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,*arg): 
        self.print_log(type='I', msg='Inititalizing %s' %(__name__)) 
        self.proplist = [ 'Rs' ];    # Properties that can be propagated from parent
        self.Rs =  100e6;            # Sampling frequency
        self.IOS=Bundle()
        self.IOS.Members['monitor_in']=IO() # Pointer for input data
        _=verilog_iofile(self,name='monitor_in', dir='in', iotype='sample', ionames=['io_monitor_in'])
        self.IOS.Members['config_out']=IO() # Pointer for input data
        _=verilog_iofile(self,name='config_out', dir='out', iotype='sample', ionames=['io_config_out'])
        self.IOS.Members['miso']=IO()       # Pointer for input data
        _=verilog_iofile(self,name='miso', dir='out', iotype='sample', ionames=['io_miso'])
        
        self.model='py';             # Can be set externally, but is not propagated
        self.par= False              # By default, no parallel processing
        self.queue= []               # By default, no parallel processing
        #Collects mosi, cs and sclk controlled by master
        self.IOS.Members['control_write']= IO() 
        #This is a placeholder, file is created by controller
        #_=verilog_iofile(self,name='control_write', dir='in', iotype='event', ionames=['reset', 'initdone', 'io_cs', 'io_mosi', 'io_sclk'])
        
        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;

        self.init()

    def init(self):
        pass
        ### Lets fix this later on
        #if self.model=='vhdl':
        #    self.print_log(type='F', msg='VHDL simulation is not supported with v1.2\n Use v1.1')

    def main(self):
        pass

    def run(self,*arg):
        if len(arg)>0:
            self.par=True      #flag for parallel processing
            self.queue=arg[0]  #multiprocessing.queue as the first argument
        if self.model=='py':
            self.main()
        else: 
          if self.model=='sv':
              #self.vlogmodulefiles=list(['async_set_register'])
              self.vlogparameters=dict([ ('g_Rs',self.Rs),]) #Defines the sample rate
              self.run_verilog()

              #if self.par:
              #   self.queue.put(self.IOS.Members[Z].Data)
              del self.iofile_bundle #Large files should be deleted
              self.IOS.Members['miso'].Data=self.IOS.Members['miso'].Data.astype('int')

          elif self.model=='vhdl':
              self.vhdlparameters=dict([ ('g_Rs',self.Rs),]) #Defines the sample rate
              self.dut=vhdl_entity(file=self.entitypath+'/vhdl/'+'spi_slave.vhd')
              #if self.par:
              #   self.queue.put(self.IOS.Members[Z].Data)
              del self.iofile_bundle #Large files should be deletedl

    def define_io_conditions(self):
        if self.model=='sv':
            # Input A is read to verilog simulation after 'initdo' is set to 1 by controller
            self.iofile_bundle.Members['monitor_in'].verilog_io_condition='initdone'
            # Output is read to verilog simulation when all of the utputs are valid, 
            # and after 'initdo' is set to 1 by controller
            self.iofile_bundle.Members['config_out'].verilog_io_condition_append(cond='&& initdone')
            # In Cpol0 Cpha1 miso is read with falling edge of sclk
            self.iofile_bundle.Members['miso'].verilog_io_sync='@(negedge io_sclk)\n'
            self.iofile_bundle.Members['miso'].verilog_io_condition_append(cond='&& initdone')


if __name__=="__main__":
    import matplotlib.pyplot as plt
    from  spi_slave import *
    from  spi_slave.controller import controller as spi_controller
    import pdb
    length=1024
    rs=100e6
    indata=np.random.randint(2,size=length).reshape(-1,1);
    controller=spi_controller()
    controller.Rs=rs
    controller.reset()
    controller.step_time()
    controller.start_datafeed()
    controller.step_time()
    #Should this be a string or array
    controller.write_spi(value='10110011')
    controller.step_time()
#    pdb.set_trace()


    #duts=[spi_slave() for i in range(2) ]
    duts=[spi_slave() for i in range(1) ]
    duts[0].model='sv'
    #duts[0].model='py'
    #duts[1].model='vhdl'
    for d in duts: 
        d.Rs=rs
        d.interactive_verilog=True
        d.IOS.Members['monitor_in'].Data=indata
        d.IOS.Members['control_write']=controller.IOS.Members['control_write']
        d.init()
        d.run()

    print('Vector received is \n%s' %(d.IOS.Members['miso'].Data))

    # THIS IS A PLOT EXAMPLE FROM THE PAST
    # NOT DESIGNED FOR THE SPI SLAVE
    # Obs the latencies may be different
    #latency=[ 0 , 1 ]
    #for k in range(len(duts)):
    #    figure=plt.figure()
    #    h=plt.subplot();
    #    hfont = {'fontname':'Sans'}
    #    x = np.linspace(0,10,11).reshape(-1,1)
    #    markerline, stemlines, baseline = plt.stem(\
    #            x,indata[0:11,0],'-.'
    #        )
    #    markerline, stemlines, baseline = plt.stem(\
    #            x, duts[k].IOS.Members['Z'].Data[0+latency[k]:11+latency[k],0], '-.'
    #        )
    #    plt.setp(markerline,'markerfacecolor', 'b','linewidth',2)
    #    plt.setp(stemlines, 'linestyle','solid','color','b', 'linewidth', 2)
    #    plt.ylim(0, 1.1);
    #    plt.xlim((np.amin(x), np.amax(x)));
    #    str = "Inverter model %s" %(duts[k].model) 
    #    plt.suptitle(str,fontsize=20);
    #    plt.ylabel('Out', **hfont,fontsize=18);
    #    plt.xlabel('Sample (n)', **hfont,fontsize=18);
    #    h.tick_params(labelsize=14)
    #    plt.grid(True);
    #    printstr="./inv_%s.eps" %(duts[k].model)
    #    plt.show(block=False);
    #    figure.savefig(printstr, format='eps', dpi=300);
    input()
