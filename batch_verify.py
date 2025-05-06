import os
from verify import verify_contract


def batch_verify():
    """
    Goes through all smart contracts in
    a specific folder and verifies them,
    here we assume there is a folder called
    contracts in the same directory
    """
    
    contract_folder = "contracts"
    sol_files = [f for f in os.listdir(contract_folder) if f.endswith(".sol")]

    if not sol_files:
        print("No smart contract files found to verify in 'contracts/' folder.")
        return

    for filename in sol_files:
        contract_name = filename[:-4]  # Remove .sol
        try:
            verify_contract(contract_name)
        except Exception as e:
            print(f"Failed to verify {contract_name}: {e}")


if __name__ == "__main__":
    batch_verify()
