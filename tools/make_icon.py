import sys

from PIL import Image

SKY_TOP = (38, 52, 104, 255)
SKY_MIDDLE = (27, 37, 80, 255)
SKY_BOTTOM = (17, 23, 54, 255)

PALETTE = {
    "#": (10, 12, 28, 255),
    "*": (255, 255, 255, 255),
    "+": (150, 170, 230, 255),
    "M": (240, 236, 200, 255),
    "m": (196, 190, 150, 255),
    "Y": (255, 226, 140, 255),
    "A": (255, 184, 70, 255),
    "a": (214, 132, 40, 255),
    "G": (140, 226, 120, 255),
    "g": (74, 176, 88, 255),
    "d": (36, 116, 66, 255),
    "W": (255, 255, 255, 255),
    "r": (236, 64, 76, 255),
}

BIG = [
    "                                ",
    "                                ",
    "         *               MMM    ",
    "            r r     +   MMm     ",
    "    +        r ##      MMm      ",
    "   +*+   ###r #YA#     MMm   *  ",
    "    +   #GGG# #YA#     MMm      ",
    "       #GW#G# #YA#      MMm     ",
    "       #GGgg# #YA#       MMM    ",
    "       #Ggg#  #YA#              ",
    "       #Ggg#  #YA#   ##         ",
    "      #Ggg#   #YA#  #dG#        ",
    "      #Ggd#   #YA#   #dG#       ",
    "   *  #Ggd#   #YA#    #g#   *   ",
    "     #Gggd#   #YA#    #dG#      ",
    "     #Ggd#    #Ya#    #dd#      ",
    "     #Ggd#     ##      #g#      ",
    "     #gdd#             #g#      ",
    "     #ggd#            #dg#      ",
    "     #ggd#            #dg#      ",
    "     #gggd#           #dg#      ",
    "      #ggd#          #dgg#      ",
    "      #gggd#        #dgg#       ",
    "       #gggd###   ##dggg#       ",
    "        #gggddd###ddgdg#        ",
    "         #ggdggddgggg##         ",
    "     *    ##gggggggg#      +    ",
    "            ########      +*+   ",
    "                           +    ",
    "           +                    ",
    "                                ",
    "                                ",
]

SMALL = [
    "            MM  ",
    "       ##  Mm   ",
    " *    #YA# Mm   ",
    "   ####YA#  MM  ",
    "  #GWG#YA# #    ",
    "  #Ggg#YA##G#   ",
    "  #Ggd#YA##dG#  ",
    "  #gd##YA##dg#  ",
    " #Ggd##Ya# #g#  ",
    " #ggd# ##  #g#  ",
    "  #gd#    #dg#  ",
    "  #ggd#  ##gg#  ",
    "   #ggd##dgg#   ",
    "  + #gggggg#    ",
    "     ##gg##     ",
    "       ##       ",
]


def inside_rounded_square(x, y, size, corner):
    nearest_x = min(max(x + 0.5, corner), size - corner)
    nearest_y = min(max(y + 0.5, corner), size - corner)
    return ((x + 0.5 - nearest_x) ** 2 + (y + 0.5 - nearest_y) ** 2) ** 0.5 <= corner


def sky_color(x, y, size):
    first_edge, second_edge = size * 0.34, size * 0.66
    dither = (x + y) % 2 == 0
    if y < first_edge - 1 or (y < first_edge and dither):
        return SKY_TOP
    if y < second_edge - 1 or (y < second_edge and dither):
        return SKY_MIDDLE
    return SKY_BOTTOM


def draw_icon(rows, corner):
    size = len(rows)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        assert len(row) == size, f"row {y} has {len(row)} pixels, expected {size}"
        for x, char in enumerate(row):
            if not inside_rounded_square(x, y, size, corner):
                continue
            color = PALETTE[char] if char != " " else sky_color(x, y, size)
            image.putpixel((x, y), color)
    return image


def scaled(image, factor):
    return image.resize((image.width * factor, image.height * factor), Image.NEAREST)


def main():
    output_folder = sys.argv[1] if len(sys.argv) > 1 else "assets"
    big = draw_icon(BIG, corner=6)
    small = draw_icon(SMALL, corner=3)

    scaled(big, 8).save(f"{output_folder}/IdleDown.png")

    frames = [small, big, scaled(small, 3), scaled(big, 2), scaled(big, 4), scaled(big, 8)]
    frames[-1].save(f"{output_folder}/IdleDown.ico",
                    sizes=[frame.size for frame in frames], append_images=frames[:-1])


if __name__ == "__main__":
    main()
