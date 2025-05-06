import os
import requests
from dotenv import load_dotenv

# Load your Together API key from .env
load_dotenv()

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"
MODEL = "mistralai/Mistral-7B-Instruct-v0.2"


def read_interface_code(interface_path="interfaces/IERC20.sol"):
    if os.path.exists(interface_path):
        with open(interface_path, "r") as f:
            return f.read()
    raise FileNotFoundError(f"IERC20 interface not found at: {interface_path}")


def build_prompt():
    interface_code = read_interface_code()

    return f"""
        You are a formal methods expert writing CTL formulas for NuSMV/nuXmv.
        
        You are given the Solidity interface of an ERC-20 token:
        ------------------------------
        {interface_code}
        ------------------------------
        
        Assume this is modeled in NuSMV using only the following state variables:
        - sender_balance : integer in range 0..1000
        - receiver_balance : integer in range 0..1000
        - amount : integer in range 0..1000
        
        You must write **only CTLSPEC lines**, using these rules:
        
        1. Use CTL operators like `AG`, `AX`, `EF`, `EX`, etc., but:
           - Use **AX**, not EX, for modeling state updates caused by deterministic transfers.
           - Only use `EX` or `EF` for non-deterministic or optional behaviors (which we do not model here).
        
        2. Use `next(variable)` to refer to next-state values — do **not** use primes or symbolic events.
        
        3. Use **only** the following variable names: `sender_balance`, `receiver_balance`, and `amount`.
        
        4. Do not reference undeclared variables like `total_supply`, or use Solidity constructs like `Transfer(...)`.
        
        5. Do not include comments or explanations — only valid CTLSPEC lines.
        
        Your CTL specs should:
        - Enforce that transfer only happens when `sender_balance >= amount`
        - Ensure balances update correctly and symmetrically
        - Ensure the total tokens remain constant
        - Constrain sender to only lose and receiver to only gain (bounded)
        
        Correct example lines:
        CTLSPEC AG (sender_balance + receiver_balance = 1000)
        CTLSPEC AG (sender_balance >= amount -> AX (next(sender_balance) = sender_balance - amount))
        CTLSPEC AG (sender_balance >= amount -> AX (next(receiver_balance) = receiver_balance + amount))
        CTLSPEC AX (next(sender_balance) + next(receiver_balance) = sender_balance + receiver_balance)
        CTLSPEC AG (next(sender_balance) <= sender_balance)
        CTLSPEC AG (next(receiver_balance) <= receiver_balance + amount)
        
        Only output valid CTLSPEC lines compatible with NuSMV.
        """


def generate_ctl_from_interface(contract_path, ctl_output_path):
    prompt = build_prompt()

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant for smart contract verification."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    print(f"Sending prompt to Together.ai (Mistral)...")
    response = requests.post(TOGETHER_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        ctl_raw = result['choices'][0]['message']['content']

        # Clean up result: remove all non-CTLSPEC lines
        ctl_lines = ctl_raw.strip().splitlines()
        valid_ctl_lines = [
            line.strip()
            for line in ctl_lines
            if line.strip().startswith("CTLSPEC") and "'" not in line and "next(" in line
        ]

        if not valid_ctl_lines:
            raise ValueError("No valid CTLSPEC lines returned by model.")

        # Write cleaned CTLSPECs to file
        with open(ctl_output_path, "w") as f:
            f.write("\n".join(valid_ctl_lines))

        print(f"CTL spec written to {ctl_output_path}")
    else:
        print(f"API Error: {response.status_code}")
        print(response.text)
        raise Exception("CTL generation failed")
