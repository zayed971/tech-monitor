"""Compare real checkout quotes; unknown shipping/tax never becomes zero."""
import math

def landed_egp(item_usd,shipping_usd,import_charges_usd,usd_egp,card_fee_pct=0,extra_egp=0):
    values=[item_usd,shipping_usd,import_charges_usd,usd_egp,card_fee_pct,extra_egp]
    if any(v is None for v in values): return None
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in values) or usd_egp==0:
        raise ValueError('Quote amounts must be finite nonnegative numbers and the exchange rate positive.')
    return round((item_usd+shipping_usd+import_charges_usd)*usd_egp*(1+card_fee_pct/100)+extra_egp,2)

def maximum_delivered_usd(local_egp,usd_egp,card_fee_pct=0,saving_pct=0):
    if not 0<=saving_pct<100 or card_fee_pct<0 or usd_egp<=0: raise ValueError('Invalid comparison inputs.')
    return round(local_egp*(1-saving_pct/100)/(usd_egp*(1+card_fee_pct/100)),2)
