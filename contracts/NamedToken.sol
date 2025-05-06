// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract NamedToken {
    mapping(address => uint256) public balances;

    constructor() {
        balances[msg.sender] = 600;
        balances[address(0xABC)] = 400;
    }

    function transfer(address recipient, uint256 value) public returns (bool) {
        require(balances[msg.sender] >= value, "Insufficient");
        balances[msg.sender] -= value;
        balances[recipient] += value;
        return true;
    }
}
