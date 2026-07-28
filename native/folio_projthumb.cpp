#include <cstdint>
#include <cstdlib>
#include <cstring>

#include <QImage>

#include <kis_types.h>
#include <kis_node.h>
#include <kis_paint_device.h>

/* Minimal declaration of libkis Node (global namespace).
   We never construct one — Python hands us a Node* via sip.unwrapinstance,
   and we only call node()->node() to get the underlying KisNodeSP. */
class Node : public QObject {
public:
    KisNodeSP node() const;
};

extern "C" {

int folio_projection_thumbnail(uintptr_t node_ptr, int req_w, int req_h,
                               unsigned char** out, int* outw, int* outh, int* outstride)
{
    *out = nullptr;
    *outw = 0;
    *outh = 0;
    *outstride = 0;

    Node* n = reinterpret_cast<Node*>(node_ptr);
    if (!n) return 0;

    KisNodeSP kn = n->node();
    if (!kn) return 0;

    /* Use original() — only this layer's own content (children for groups,
       raw pixels for paint layers, with masks applied). Never use projection()
       as fallback because it may include merged sibling layers below. */
    KisPaintDeviceSP dev = kn->original();
    if (!dev) return 0;

    QImage img = dev->createThumbnail(req_w, req_h, Qt::KeepAspectRatio);
    if (img.isNull()) return 0;

    QImage rgba = img.convertToFormat(QImage::Format_RGBA8888);
    int width = rgba.width();
    int height = rgba.height();
    int stride = rgba.bytesPerLine();
    int size = stride * height;

    unsigned char* buf = static_cast<unsigned char*>(std::malloc(size));
    if (!buf) return 0;
    std::memcpy(buf, rgba.constBits(), static_cast<size_t>(size));

    *out = buf;
    *outw = width;
    *outh = height;
    *outstride = stride;
    return 1;
}

void folio_free(void* p)
{
    std::free(p);
}

}
