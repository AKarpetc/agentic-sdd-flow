namespace Orders.Api.Services;

/// <summary>Offset arithmetic for 1-based pages.</summary>
internal static class PageMath
{
    public static int Skip(int page, int size)
    {
        return page * size;
    }
}
