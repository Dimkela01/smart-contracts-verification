// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MyToken {
    mapping(address => uint256) private balances;

    constructor() {
        balances[msg.sender] = 500;
        balances[address(0x123)] = 500;
    }

    function transfer(address recipient, uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient");
        balances[msg.sender] -= amount;
        balances[recipient] += amount;
    }
}
