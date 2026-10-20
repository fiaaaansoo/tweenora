#include "rive/span.hpp"

namespace assets
{
constexpr static unsigned int test_image_png_len = 26065;
extern unsigned char test_image_png_data[test_image_png_len];
inline static rive::Span<uint8_t> test_image_png()
{
    return {test_image_png_data, test_image_png_len};
}
}; // namespace assets
