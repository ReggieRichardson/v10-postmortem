import subprocess
import argparse
import os
import time
import re

numericalVersion=0
pmCommitDate="Date"
pmCommit="Hash Value"
pmCommitURL="Link Here"
def print_postmortem_version(): 
    print("Postmortem Version: " + str(numericalVersion) + ", Date: " + pmCommitDate + ", URL: " + pmCommitURL)

#Confirm whether oc or kubectl exists and choose which command tool to use based on that
try: 
    ocCheck = subprocess.check_output("which oc", shell=True)
    kubectl="oc"
    # Checking to see if oc is logged in
    checkLogin = subprocess.run(f"{kubectl} whoami", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if checkLogin.returncode == 1: 
        print("Error: oc whoami failed. This script requires you to be logged in to the server. EXITING...")
        exit(1)
except subprocess.CalledProcessError as ocNotFound: 
    try:
        kubectlCheck = subprocess.check_output("which kubectl", shell=True)
        kubectl="kubectl"
    except subprocess.CalledProcessError as kubectlNotFound: 
        print("Unable to locate the command [kubectl] nor [oc] in the path.  Either install or add it to the path.  EXITING...")
        exit(1)

#Check if kubectl-cnp plugin is installed
def is_kubectl_cnp_plugin():
    cnpCheck = subprocess.run("which kubectl-cnp", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if cnpCheck.returncode == 0: 
        print("kubectl-cnp plugin found")
    else: 
        print("kubectl-cnp plugin not found")
        print("Download and Install kubectl-cnp plugin (y/n)? ")
        userInput = input()
        match userInput:
            case "y": 
                print("Proceeding...")
                print("Executing: curl -sSfL https://github.com/EnterpriseDB/kubectl-cnp/raw/main/install.sh | sudo sh -s -- -b /usr/local/bin")
                subprocess.run("curl -sSfL \
                    https://github.com/EnterpriseDB/kubectl-cnp/raw/main/install.sh | \
                    sudo sh -s -- -b /usr/local/bin", shell=True)
            case _:
                print("Exiting... please install kubectl-cnp plugin and add it to your PATH, see https://www.enterprisedb.com/docs/postgres_for_kubernetes/latest/kubectl-plugin.")
                exit(1)

#Check to see if it an OCP cluster
ocp = False 
route = "route.openshift.io"
ocpValue = subprocess.run(f"{kubectl} api-resources | grep -q {route}", shell=True)
if ocpValue.returncode == 0: 
    ocp = True

# Add Flags
flags = argparse.ArgumentParser(add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter, description=('''
Available switches:

--specific-namespaces:   Target only the listed namespaces for the data collection.  Example:  --specific-namespaces=dev1,dev2,dev3
--extra-namespaces:      Extra namespaces separated with commas.  Example:  --extra-namespaces=dev1,dev2,dev3
--log-limit:             Set the number of lines to collect from each pod logs.
--no-prompt:             Do not prompt to report auto-detected namespaces.
--performance-check:     Set to run performance checks.
--no-history:            Do not collect user history.

--ova:                   Only set if running inside an OVA deployment.
--pull-appliance-logs:   Call [apic logs] command then package into archive file.

--collect-private-keys:  Include tls.key members in TLS secrets from targeted namespaces.  Due to sensitivity of data, do not use unless requested by support.
--collect-crunchy:       Collect Crunchy mustgather.
--collect-edb:           Collect EDB mustgather.

--diagnostic-all:        Set to enable all diagnostic data.
--diagnostic-manager:    Set to include additional manager specific data.
--diagnostic-gateway:    Set to include additional gateway specific data.
--diagnostic-portal:     Set to include additional portal specific data.
--diagnostic-analytics:  Set to include additional analytics specific data.

--debug:                 Set to enable verbose logging.
--no-script-check:       Set to disable checking if the postmortem scripts are up to date.

--version:               Show postmortem version
'''))
flags.add_argument("--help", "-h", action='help', help=argparse.SUPPRESS)
flags.add_argument("--specific-namespaces", help=argparse.SUPPRESS)
flags.add_argument("--extra-namespaces", help=argparse.SUPPRESS)
flags.add_argument("--log-limit", type=int, help=argparse.SUPPRESS)
flags.add_argument("--no-prompt", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--performance-check", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--no-history", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--ova", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--pull-appliance-logs", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--collect-private-keys", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--collect-crunchy", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--collect-edb", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--diagnostic-all", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--diagnostic-manager", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--diagnostic-gateway", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--diagnostic-portal", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--diagnostic-analytics", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--no-script-check", action="store_true", help=argparse.SUPPRESS)
flags.add_argument("--version", action="store_true", help=argparse.SUPPRESS)

flagArgs = flags.parse_args() 
config = vars(flagArgs)

def warn_if_script_is_not_latest(localScript, remoteScript):
    if flagArgs.no_script_check == True: 
        return
    
    localScriptHash=subprocess.run(f"sha256sum {localScript} | cut -d ' ' -f1", shell=True)
    response=subprocess.Popen(f"curl -s --connect-timeout 5 {remoteScript}", shell=True, stdout=subprocess.PIPE, text=True)

    if response.returncode == 0:
        print("here")

#Creating Namespace List
namespaceList=[]

#Setting flag information
if flagArgs.debug: 
    #maybe pdb??
    print("Originally set -x")

if flagArgs.ova: 
    if os.geteuid() != 0: 
        print("This script must be run as root.")
        exit(1)
    flagArgs.no_prompt = True
    namespaceList.append("kube-system")

if flagArgs.diagnostic_all: 
    flagArgs.diagnostic_manager = True
    flagArgs.diagnostic_gateway = True
    flagArgs.diagnostic_portal = True 
    flagArgs.diagnostic_analytics = True

if flagArgs.log_limit:
    limit=flagArgs.log_limit
    logLimit=f"--tail={limit}"

if flagArgs.specific_namespaces: 
    additionalNamespaces = flagArgs.specific_namespaces.split(",")
    namespaceList.extend(additionalNamespaces)
    flagArgs.no_prompt = True

if flagArgs.extra_namespaces:
    additionalNamespaces = flagArgs.extra_namespaces.split(",") 
    namespaceList.extend(additionalNamespaces)
    flagArgs.no_prompt = True


if flagArgs.collect_crunchy: 
    scriptLocation=os.getcwd()+"/crunchy_gather.py"
    if not os.path.exists(scriptLocation): 
        print("Unable to locate script [crunchy_gather.py] in current directory.  Download from GitHub repository.  Exiting...")
        exit(1)
    warn_if_script_is_not_latest("crunchy_gather.py", "https://raw.githubusercontent.com/ibm-apiconnect/v10-postmortem/master/crunchy_gather.py")
    #chmod +x SCRIPT_LOCATION
        
if flagArgs.collect_edb: 
    is_kubectl_cnp_plugin()
    scriptLocation=os.getcwd()+"/edb_mustgather.sh"
    if not os.path.exists(scriptLocation): 
        print("Unable to locate script [crunchy_gather.py] in current directory.  Download from GitHub repository.  Exiting...")
        exit(1)
    warn_if_script_is_not_latest("edb_mustgather.sh", "https://raw.githubusercontent.com/ibm-apiconnect/v10-postmortem/master/edb_mustgather.sh")
    #chmod +x SCRIPT_LOCATION
        
if flagArgs.version: 
    print_postmortem_version() 
    exit(0)

if not flagArgs.debug: 
    print("Originally had set +e which instructs the shell to exit immediately if any command or pipeline returns a non zero exit status")

#Printing Postmortem Version
print_postmortem_version()
print("using [" + kubectl + "] command for cluster cli")

warn_if_script_is_not_latest(os.path.basename(__file__), "https://raw.githubusercontent.com/ibm-apiconnect/v10-postmortem/master/generate_postmortem.sh")

#====================================== Confirm pre-reqs and init variables ======================================
#------------------------------- Make sure all necessary commands exists ------------------------------

zipCheck = subprocess.run("which zip", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if zipCheck.returncode == 1: 
    tarCheck = subprocess.run("which tar", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if tarCheck.returncode == 1: 
        print("Unable to locate either command [tar] / [zip] in the path.  Either install or add it to the path.  EXITING...")
        exit(1)

if flagArgs.diagnostic_manager: 
    edbClusterName=subprocess.run(f"{kubectl} get cluster --all-namespaces -o=jsonpath='{{.items[0].metadata.name}}' 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    if edbClusterName.returncode != 0: 
        flagArgs.collect_crunchy = True
        scriptLocation=scriptLocation=os.getcwd()+"/crunchy_gather.py"
    else: 
        flagArgs.collect_edb = True
        is_kubectl_cnp_plugin() 
        scriptLocation=os.getcwd()+"/edb_mustgather.sh"
    if not os.path.exists(scriptLocation): 
        print(f"Unable to locate script {scriptLocation} in current directory.  Download from GitHub repository.  Exiting...")
        exit(1)
#------------------------------------------------------------------------------------------------------

#------------------------------------------ custom functions ------------------------------------------
def generateXMLForErrorReport(XMLPath): 
    print("inside generate XML for error Report")
#------------------------------------------------------------------------------------------------------

#------------------------------------------- Set variables --------------------------------------------
logPath="/tmp"
currentPath=os.getcwd()
timestamp=time.strftime("%Y%m%dT%H%M%S%Z")
tempName=f"postmortem-{timestamp}"
tempPath=f"{logPath}/{tempName}"

if not namespaceList: 
    namespaceList.append("kube-system")

autoDetect = 1

archiveFile=""
errorReportSleepTimeout = 30

minDockerVersion="17.03"
minKubeletVersion="1.17"

#maybe change this
def colorYellow(text): 
    return("\033[33m{}\033[00m" .format(text))
#maybe change this
def colorWhite(text): 
    return("\033[37m{}\033[00m" .format(text))

#------------------------------------------------------------------------------------------------------

#------------------------------------------- Clean up area --------------------------------------------
def cleanup(): 
    print(f"Cleaning up.  Removing directory {tempPath}.")
    os.rmdir(tempPath)
    print("missing trap cleanup EXIT")
#------------------------------------------------------------------------------------------------------
#=================================================================================================================

print("Generating postmortem, please wait...")

os.makedirs(tempPath)

#determine if metrics is installed 
metricsCheck=subprocess.run(f'{kubectl} get pods --all-namespaces 2>/dev/null | egrep -q "metrics-server|openshift-monitoring"', shell=True)
if metricsCheck.returncode == 0: 
    outputMetrics = 0
else:
    outputMetrics = 1

#Namespaces 
getNamespacesCommand=subprocess.run(f"{kubectl} get ns 2>/dev/null -oname", shell=True, stdout=subprocess.PIPE, encoding='utf-8')
output = list(getNamespacesCommand.stdout.replace("namespace/", '').split())
namespaceOptions=["rook-ceph", "rook-ceph-system", "ibm-common-services", "openshift-marketplace", "openshift-operators", "openshift-operator-lifecycle-manager", "certmanager"]
namespaceList.extend([value for value in output if value in namespaceOptions]) # intersect command


#================================================= pull ova data =================================================


#------------------------------------------------------------------------------------------------------


#============================================= pull kubernetes data ==============================================
#----------------------------------------- create directories -----------------------------------------
k8sData=f"{tempPath}/kubernetes"

k8sCluster=f"{k8sData}/cluster"
k8sNamespaces=f"{k8sData}/namespaces"
k8sVersion=f"{k8sData}/versions"

k8sClusterNodeData=f"{k8sCluster}/nodes"
k8sClusterListData=f"{k8sCluster}/lists"
k8sClusterRoleData=f"{k8sCluster}/clusterroles"
k8sClusterRoleBindingData=f"{k8sCluster}/clusterrolebindings"

k8sClusterCRDData=f"{k8sCluster}/crd"
k8sClusterCRDDescribeData=f"{k8sClusterCRDData}/describe"

k8sClusterPVData=f"{k8sCluster}/pv"
k8sClusterPVDescribeData=f"{k8sClusterPVData}/describe"

k8sClusterStorageClassData=f"{k8sCluster}/storageclasses"
k8sClusterStorageClassDescribeData=f"{k8sClusterStorageClassData}/describe"

k8sClusterPerformance=f"{k8sCluster}/performance"

k8sClusterValidatingWebHookConfigurations=f"{k8sCluster}/validatingwebhookconfigurations"
k8sClusterValidatingWebHookYAMLOutput=f"{k8sClusterValidatingWebHookConfigurations}/yaml"

k8sClusterMutatingWebHookConfigurations=f"{k8sCluster}/mutatingwebhookconfigurations"
k8sClusterMutatingWebHookYAMLOutput=f"{k8sClusterMutatingWebHookConfigurations}/yaml"

os.makedirs(f"{k8sVersion}")

os.makedirs(f"{k8sClusterNodeData}")
os.makedirs(f"{k8sClusterListData}")
os.makedirs(f"{k8sClusterRoleData}")
os.makedirs(f"{k8sClusterRoleBindingData}")

os.makedirs(f"{k8sClusterCRDDescribeData}")
os.makedirs(f"{k8sClusterPVDescribeData}")
os.makedirs(f"{k8sClusterStorageClassDescribeData}")

os.makedirs(f"{k8sClusterPerformance}")

os.makedirs(f"{k8sClusterValidatingWebHookYAMLOutput}")
os.makedirs(f"{k8sClusterMutatingWebHookYAMLOutput}")

#---------------------------------- collect namespace specific data -----------------------------------
for namespace in namespaceList: 
    
    k8sNamespacesSpecific=f"{k8sNamespaces}/{namespace}"

    k8sNamespacesDeploymentData=f"{k8sNamespacesSpecific}/deployments"
    k8sNamespacesDeploymentYAMLOutput=f"{k8sNamespacesDeploymentData}/yaml"
    k8sNamespacesDeploymentDescribeData=f"{k8sNamespacesDeploymentData}/describe"

    os.makedirs(f"{k8sNamespacesDeploymentYAMLOutput}")
    os.makedirs(f"{k8sNamespacesDeploymentDescribeData}")



    getCommand=subprocess.run(f"{kubectl} get deployments -n {namespace} 2>/dev/null", shell=True, stdout=subprocess.PIPE, encoding='utf-8')
    if getCommand.returncode == 0 and len(getCommand.stdout) > 0:
        file=open(f"{k8sNamespacesDeploymentData}/deployment.out", "w")
        file.write(getCommand.stdout)

        describeCommand = subprocess.run(f"{kubectl} describe deployments -n {namespace}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding='utf-8')
        if describeCommand.returncode == 0: 
            resultList=list(describeCommand.stdout.split("\n\n\n"))
            for item in resultList: 
                title = re.sub("Name:", "", item).strip().splitlines()
                with open(f"{k8sNamespacesDeploymentDescribeData}/{title[0]}.out", "w") as filedata:
                    filedata.write("%s\n" % item)
                    filedata.close

        yamlCommand = subprocess.run(f"{kubectl} get deployment -o yaml -n {namespace}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding='utf-8')
        if yamlCommand.returncode == 0:
            resultList=re.split('\n-', yamlCommand.stdout)
            for item in resultList[1:]:
                title = re.search(r'    name: ([\w\.-]+)', item)
                title = title.group(0).replace("    name: ","")
                with open(f"{k8sNamespacesDeploymentYAMLOutput}/{title}.yaml", "w") as filedata:
                    filedata.write("%s\n" % ("- apiVersion: apps/v1\n  kind: Deployment\n" + item))
                    filedata.close

