.class final Lcom/twobtn/TwoButtonPatch$SwallowTouches;
.super Ljava/lang/Object;
.source "TwoButtonPatch.java"

# implements
.implements Landroid/view/View$OnTouchListener;

# Consumes every touch on the hidden Recents slot so it never clicks.

.method constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method

.method public onTouch(Landroid/view/View;Landroid/view/MotionEvent;)Z
    .locals 0

    const/4 p0, 0x1

    return p0
.end method
