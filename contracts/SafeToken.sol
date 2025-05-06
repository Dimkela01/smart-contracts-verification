// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SafeToken {
    error NotEnough();

    mapping(address => uint256) public balances;

    constructor() {
        balances[msg.sender] = 1000;
    }

    function transfer(address to, uint256 amount) public {
        if (balances[msg.sender] < amount) revert NotEnough();
        balances[msg.sender] -= amount;
        balances[to] += amount;
    }
}
