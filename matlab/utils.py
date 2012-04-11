import subprocess
import re

class Matlab:
    def __init__(self,exec_path,matlab_path='.',fail_fast=True):
        self.exec_path = exec_path
        self.matlab_path = matlab_path
        self.fail_fast = fail_fast
        self.output_separator = '__BEGIN MATLAB OUTPUT__'
    def run(self,command):
        env = dict(MATLABPATH=self.matlab_path)
        try:
            cmd = '%s -nodisplay -r "disp(\'%s\'), %s, quit"' % (self.exec_path, self.output_separator, command)
            p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
            out, _ = p.communicate()
            _, content = re.split(self.output_separator,out)
            return re.split('\n',content.strip())
        except:
            if self.fail_fast:
                raise
