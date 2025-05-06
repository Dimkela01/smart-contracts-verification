import os
import shutil
from subprocess import run
from extract_model import generate_smv_from_sol
from mistral_wrapper import generate_ctl_from_interface


def combine_files(model_path, ctl_path, combined_path):
    with open(model_path, "r") as f1, open(ctl_path, "r") as f2:
        combined = f1.read().strip() + "\n\n" + f2.read().strip()
    with open(combined_path, "w") as fout:
        fout.write(combined)
    print(f"Combined model+CTL saved to {combined_path}")


def run_nuxmv(input_file, output_file):
    import shutil
    import tempfile
    import os

    nuxmv_exe = shutil.which("nuXmv") or shutil.which("nuxmv.exe")
    if not nuxmv_exe:
        fallback_path = r"C:\nuXmv-2.1.0-win64\nuXmv-2.1.0-win64\bin\nuXmv.exe"
        if os.path.exists(fallback_path):
            nuxmv_exe = fallback_path
        else:
            raise FileNotFoundError("nuXmv executable not found.")

    # Use absolute path to .smv file (Windows-safe)
    abs_input_path = os.path.abspath(input_file)

    # Create temporary .cmds file with proper commands
    cmds = f"""
read_model -i "{abs_input_path}"
flatten_hierarchy
encode_variables
build_model
check_ctlspec
quit
"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".cmds", mode="w") as cmd_file:
        cmd_file.write(cmds)
        cmd_file_path = cmd_file.name

    # Run nuXmv with -source
    result = run([nuxmv_exe, "-source", cmd_file_path], capture_output=True, text=True)

    # Save stdout to result file
    with open(output_file, "w") as f:
        f.write(result.stdout)

    # Optional: also print to terminal
    print(f"nuXmv result saved to {output_file}")
    print("--- nuXmv output preview ---")
    print(result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout)


def verify_contract(contract_name):
    contract_path = f"contracts/{contract_name}.sol"
    smv_path = f"outputs/{contract_name}.smv"
    ctl_path = f"outputs/{contract_name}.ctl"
    combined_path = f"outputs/{contract_name}_combined.smv"
    result_path = f"outputs/{contract_name}_result.txt"

    print(f"\nVerifying contract: {contract_name}")

    try:
        # Generate SMV model
        generate_smv_from_sol(contract_path, smv_path)

        # Generate CTL spec via Mistral
        generate_ctl_from_interface(contract_path, ctl_path)

        # Combine model and spec
        combine_files(smv_path, ctl_path, combined_path)

        # Run nuXmv
        #run_nuxmv(combined_path, result_path)

    except Exception as e:
        print(f"Failed to verify {contract_name}: {e}")