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
   
    # Rebalance every day, 1 hour before market close.
    schedule_function(
        my_rebalance,
        date_rules.week_start(),
        time_rules.market_close(hours=1),
    )
    
    # Record tracking variables at the end of each day.
    schedule_function(
        my_record_vars,
        date_rules.every_day(),
        time_rules.market_close(),
    )
    
    # Loss stop function before market close.
#    schedule_function(
#        loss_stop,
#        date_rules.every_day(),
#        time_rules.market_close(hours=1),
#    )
    

    # Create our pipeline and attach it to our algorithm.
    my_pipe = make_pipeline()
    attach_pipeline(my_pipe, 'my_pipeline')

    
#def loss_stop(context,data):
   
#    if context.portfolio.positions:
#        for position_id in context.portfolio.positions:
#            if context.portfolio.positions[position_id].amount > 0:
#                market_price = context.portfolio.positions[position_id].last_sale_price
#                cost_price = context.portfolio.positions[position_id].cost_basis
#                stop_price = cost_price - cost_price*0.1
#                if market_price <= stop_price:
#                    order_target(position_id, 0)
#            elif context.portfolio.positions[position_id].amount < 0:
#                market_price = context.portfolio.positions[position_id].last_sale_price
#                cost_price = context.portfolio.positions[position_id].cost_basis
#                stop_price = cost_price + cost_price*0.1
#                if market_price >= stop_price:
#                    order_target(position_id, 0)
               
              
def make_pipeline():
    # daily run
    # Base universe set to the QTradableStocksUS
    base_universe = QTradableStocksUS()
    
    #mean average 均線戰術
    mean_20 = SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=20
                                           ,mask=base_universe)
    mean_20_before = SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=19,
                                         mask=base_universe)
    mean_60 = SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=60,
                                  mask=base_universe)
    mean_60_before = SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=59,
                                  mask=base_universe)
    mean_1 = SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=1,
                                 mask=base_universe)
    
    #判斷季線趨勢
    mean_60_slope = (mean_60 - mean_60_before) / mean_60_before
    longterm_slope_rising = mean_60_slope > 0.005
    longterm_slope_droping = mean_60_slope < -0.005
    #判斷月線趨勢
    mean_20_slope = mean_20 - mean_20_before
    shortterm_slope_rising = mean_20_slope > 0.01
    shortterm_slope_droping = mean_20_slope < -0.01
    #價格穿過20ma來當作訊號搶反彈
    price_cross = (mean_1 - mean_60)/ mean_60
    buy_cross = price_cross < -0.3
    sell_cross = price_cross > 0.3
    
    #dollar vol filter 月交易來看流動性
    dollar_vol = AverageDollarVolume(window_length=30)
    high_dollar_vol = dollar_vol > 10000000
    
    #Filter to select securities to short
    shorts =  longterm_slope_droping & shortterm_slope_droping & sell_cross
    
    #Filter to select securities to long
    longs =  longterm_slope_rising & shortterm_slope_rising & buy_cross
    
    #Filter for all securities that we want to trade.
    securities_to_trade = (shorts | longs) & high_dollar_vol
    
    
    return Pipeline(columns={
            'shorts': shorts,
            'longs':longs
        },screen=securities_to_trade)

def compute_target_weights(context,data):
    weights = {}
    if context.longs and context.shorts:
        long_weight = 0.7 / len(context.longs)
        short_weight = -0.3 / len(context.shorts)
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
    constr = []
    if target_weights:
        order_optimal_portfolio(objective=opt.TargetWeights(target_weights),
                                    constraints=constr)
       


def my_record_vars(context, data):
    
    #record variables at the end of each day
    longs = 0
    shorts = 0
    for position in context.portfolio.positions.itervalues():
        if position.amount > 0:
            longs+=1
        elif position.amount < 0:
            shorts+=1
    
    record(leverage=context.account.leverage,
           long_count=longs,
           short_count=shorts
           )