// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Escrow {
    address public buyer;
    address public seller;
    address public arbiter;
    uint256 public amount;
    bool public isFunded;
    bool public isReleased;

    constructor(address _seller, address _arbiter) payable {
        buyer = msg.sender;
        seller = _seller;
        arbiter = _arbiter;
        amount = msg.value;
        isFunded = true;
    }

    function releaseToSeller() public {
        require(msg.sender == buyer || msg.sender == arbiter, "Unauthorized");
        require(isFunded && !isReleased, "Invalid state");
        isReleased = true;
        payable(seller).transfer(amount);
    }

    function refundBuyer() public {
        require(msg.sender == seller || msg.sender == arbiter, "Unauthorized");
        require(isFunded && !isReleased, "Invalid state");
        isReleased = true;
        payable(buyer).transfer(amount);
    }
}