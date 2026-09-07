using Microsoft.Extensions.Options;
using Platform.Contracts;
using Pricing.Api.Configuration;

namespace Pricing.Api.Services;

/// <summary>Prices a basket from the configured price list and applies the promotions it qualifies for.</summary>
internal sealed class PricingService
{
    private readonly IOptionsSnapshot<PricingSettings> _settings;

    public PricingService(IOptionsSnapshot<PricingSettings> settings)
    {
        _settings = settings;
    }

    public QuoteOutcome Quote(QuoteRequest request)
    {
        var settings = _settings.Value;
        var subtotal = 0m;
        foreach (var line in request.Lines)
        {
            if (!settings.PriceList.TryGetValue(line.Sku, out var unitPrice))
            {
                return new QuoteOutcome(null, line.Sku);
            }

            subtotal += unitPrice * line.Quantity;
        }

        subtotal = decimal.Round(subtotal, 2, MidpointRounding.AwayFromZero);
        var discounts = Discounts(settings, subtotal);
        var total = Math.Max(0m, subtotal - discounts.Sum(discount => discount.Amount));
        return new QuoteOutcome(new QuoteResult(subtotal, discounts, decimal.Round(total, 2, MidpointRounding.AwayFromZero)), null);
    }

    private static IReadOnlyList<QuoteDiscount> Discounts(PricingSettings settings, decimal subtotal)
    {
        return settings.Promotions
            .Where(promotion => subtotal >= promotion.MinSubtotal)
            .Select(promotion => new QuoteDiscount(promotion.Code, Amount(promotion, subtotal)))
            .Where(discount => discount.Amount > 0m)
            .ToList();
    }

    private static decimal Amount(PromotionSettings promotion, decimal subtotal)
    {
        var raw = promotion.Kind.Equals("Percentage", StringComparison.OrdinalIgnoreCase)
            ? subtotal * promotion.Value / 100m
            : promotion.Value;
        return decimal.Round(Math.Min(raw, subtotal), 2, MidpointRounding.AwayFromZero);
    }
}
