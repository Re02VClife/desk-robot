// image_to_jpeg.h - 图像到JPEG转换的高效编码接口
// 节省约8KB SRAM的JPEG编码实现
// 已迁移至 esp_new_jpeg 原生 jpeg_pixel_format_t 类型（不再依赖 V4L2）
#pragma once
#include "sdkconfig.h"
#ifndef CONFIG_IDF_TARGET_ESP32

#include <stdint.h>
#include <stddef.h>
#include "esp_jpeg_common.h"

// esp_new_jpeg 原生格式常量（jpeg_pixel_format_t 枚举值，定义见 esp_jpeg_common.h）：
//   JPEG_PIXEL_FORMAT_GRAY       = 0  — 灰度
//   JPEG_PIXEL_FORMAT_RGB888     = 1  — RGB24
//   JPEG_PIXEL_FORMAT_RGBA       = 2  — RGBA
//   JPEG_PIXEL_FORMAT_YCbYCr     = 3  — YUYV (packed YUV422)
//   JPEG_PIXEL_FORMAT_YCbY2YCrY2 = 4  — packed YUV420
//   JPEG_PIXEL_FORMAT_RGB565_BE  = 5  — RGB565 big-endian
//   JPEG_PIXEL_FORMAT_RGB565_LE  = 6  — RGB565 little-endian
//   JPEG_PIXEL_FORMAT_CbYCrY     = 7  — UYVY (packed YUV422)

// 特殊格式（esp_new_jpeg 无直接对应，用于内部格式转换标记）
#define JPEG_PIXEL_FORMAT_YUV422P ((jpeg_pixel_format_t)100) // YUV422 planar → YUYV
#define JPEG_PIXEL_FORMAT_JPEG    ((jpeg_pixel_format_t)101) // JPEG 透传（摄像头已输出JPEG）

#ifdef __cplusplus
extern "C"
{
#endif

    // JPEG输出回调函数类型
    // arg: 用户自定义参数, index: 当前数据索引, data: JPEG数据块, len: 数据块长度
    // 返回: 实际处理的字节数
    typedef size_t (*jpg_out_cb)(void *arg, size_t index, const void *data, size_t len);

    /**
     * @brief 将图像格式高效转换为JPEG
     *
     * @param src       源图像数据
     * @param src_len   源图像数据长度
     * @param width     图像宽度
     * @param height    图像高度
     * @param format    图像格式 (JPEG_PIXEL_FORMAT_RGB565_LE, JPEG_PIXEL_FORMAT_RGB888 等)
     * @param quality   JPEG质量 (1-100)
     * @param out       输出JPEG数据指针 (需要调用者释放)
     * @param out_len   输出JPEG数据长度
     *
     * @return true 成功, false 失败
     */
    bool image_to_jpeg(uint8_t *src, size_t src_len, uint16_t width, uint16_t height,
                       jpeg_pixel_format_t format, uint8_t quality, uint8_t **out, size_t *out_len);

    /**
     * @brief 将图像格式转换为JPEG（回调版本）
     *
     * @param src       源图像数据
     * @param src_len   源图像数据长度
     * @param width     图像宽度
     * @param height    图像高度
     * @param format    图像格式
     * @param quality   JPEG质量 (1-100)
     * @param cb        输出回调函数
     * @param arg       传递给回调函数的用户参数
     *
     * @return true 成功, false 失败
     */
    bool image_to_jpeg_cb(uint8_t *src, size_t src_len, uint16_t width, uint16_t height,
                          jpeg_pixel_format_t format, uint8_t quality, jpg_out_cb cb, void *arg);

#ifdef __cplusplus
}
#endif

#endif // ndef CONFIG_IDF_TARGET_ESP32
