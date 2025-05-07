// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract BuggyToken {
    mapping(address => uint256) public balances;

    constructor() {
        balances[msg.sender] = 1000;
    }

    function transfer(address to, uint256 amount) public {
        balances[to] += amount;
        require(balances[msg.sender] >= amount, "Not enough");
        balances[msg.sender] -= amount;
    }
}
