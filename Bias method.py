#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quantopian backtest code

@author: dpong
"""

from quantopian.algorithm import order_optimal_portfolio
from quantopian.algorithm import attach_pipeline, pipeline_output
from quantopian.pipeline import Pipeline
from quantopian.pipeline.data.builtin import USEquityPricing
from quantopian.pipeline.factors import SimpleMovingAverage,AverageDollarVolume
from quantopian.pipeline.filters import QTradableStocksUS
import quantopian.optimize as opt


def initialize(context):
   
    # Rebalance every day, 1 hour after market open.
    schedule_function(
        my_rebalance,
        date_rules.week_start(),
        time_rules.market_open(),
    )

    # Record tracking variables at the end of each day.
    schedule_function(
        my_record_vars,
        date_rules.every_day(),
        time_rules.market_close(),
    )

    # Create our pipeline and attach it to our algorithm.
    my_pipe = make_pipeline()
    attach_pipeline(my_pipe, 'my_pipeline')


def make_pipeline():

    # Base universe set to the QTradableStocksUS
    base_universe = QTradableStocksUS()
    
    #mean average difference 用乖離當作判斷依據
    mean_10 = SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=10
                                           ,mask=base_universe)
    mean_30 = SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=30,
                                  mask=base_universe)
    percent_diff = (mean_10 - mean_30) / mean_30
    
    
    #dollar vol filter 月交易來看流動性
    dollar_vol = AverageDollarVolume(window_length=30)
    high_dollar_vol = dollar_vol > 10000000
    
    #Filter to select securities to short
    shorts = percent_diff.top(100, mask=high_dollar_vol)
    
    #Filter to select securities to long
    longs = percent_diff.bottom(100, mask=high_dollar_vol)
    
    #Filter for all securities that we want to trade.
    securities_to_trade = (shorts | longs) & high_dollar_vol
    
    
    return Pipeline(columns={
            'shorts': shorts,
            'longs':longs
        },screen=securities_to_trade)

def compute_target_weights(context,data):
    weights = {}
    if context.longs and context.shorts:
        long_weight = 0.5 / len(context.longs)
        short_weight = -0.5 / len(context.shorts)
    else:
        return weights
    
    for security in context.portfolio.positions:
        if security not in context.longs and security not in context.shorts and data.can_trade(security):
            weights[security] = 0
    
    for security in context.longs:
        weights[security] = long_weight
        
    for security in context.shorts:
        weights[security] = short_weight
    
    return weights


def before_trading_start(context, data):
    
    #get pipeline result everyday
    pipe_result = pipeline_output('my_pipeline')
    
    context.longs=[]
    for security in pipe_result[pipe_result['longs']].index.tolist():
        if data.can_trade(security):
            context.longs.append(security)
    context.shorts=[]
    for security in pipe_result[pipe_result['shorts']].index.tolist():
        if data.can_trade(security):
            context.shorts.append(security)


def my_rebalance(context, data):
    
    #rebalance weekly
    target_weights = compute_target_weights(context, data)
    
    if target_weights:
        order_optimal_portfolio(objective=opt.TargetWeights(target_weights),constraints=[])
       


def my_record_vars(context, data):
    
    #record variables at the end of each day
    longs = shorts = 0
    for position in context.portfolio.positions.itervalues():
        if position.amount > 0:
            longs+=1
        elif position.amount < 0:
            shorts+=1
    
    record(leverage=context.account.leverage,
           long_count=longs,
           short_count=shorts
           )