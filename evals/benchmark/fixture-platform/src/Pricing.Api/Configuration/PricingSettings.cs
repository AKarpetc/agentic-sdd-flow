namespace Pricing.Api.Configuration;

/// <summary>The catalogue prices and the promotions marketing may change without a deploy.</summary>
internal sealed class PricingSettings
{
    public Dictionary<string, decimal> PriceList { get; set; } = new();

    public List<PromotionSettings> Promotions { get; set; } = new();
}
