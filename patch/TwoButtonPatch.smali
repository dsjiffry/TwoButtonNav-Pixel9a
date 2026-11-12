.class public final Lcom/twobtn/TwoButtonPatch;
.super Ljava/lang/Object;
.source "TwoButtonPatch.java"

# Helper injected into Pixel Launcher by the Two-Button Navigation builder.
#
# In 2-button mode (config_navBarInteractionMode == 1) the taskbar Recents button
# is neutralised so the bar shows back + home, like Android 9:
#   - visibility INVISIBLE (keeps its slot, so home stays centred)
#   - no icon, so it draws nothing even when Launcher3's fade animations
#     (AlphaUpdateListener) later flip it back to VISIBLE on lock/unlock
#   - swallows every touch, so the empty slot never opens recents
#   - hidden from accessibility services

.method public static hideRecentsIfTwoButton(Landroid/view/View;)V
    .locals 4

    if-eqz p0, :cond_done

    invoke-virtual {p0}, Landroid/view/View;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    const-string v1, "config_navBarInteractionMode"

    const-string v2, "integer"

    const-string v3, "android"

    invoke-virtual {v0, v1, v2, v3}, Landroid/content/res/Resources;->getIdentifier(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)I

    move-result v1

    if-eqz v1, :cond_done

    invoke-virtual {v0, v1}, Landroid/content/res/Resources;->getInteger(I)I

    move-result v1

    const/4 v2, 0x1

    if-ne v1, v2, :cond_done

    const/4 v2, 0x4

    invoke-virtual {p0, v2}, Landroid/view/View;->setVisibility(I)V

    instance-of v2, p0, Landroid/widget/ImageView;

    if-eqz v2, :cond_touch

    move-object v2, p0

    check-cast v2, Landroid/widget/ImageView;

    const/4 v3, 0x0

    invoke-virtual {v2, v3}, Landroid/widget/ImageView;->setImageDrawable(Landroid/graphics/drawable/Drawable;)V

    :cond_touch
    new-instance v2, Lcom/twobtn/TwoButtonPatch$SwallowTouches;

    invoke-direct {v2}, Lcom/twobtn/TwoButtonPatch$SwallowTouches;-><init>()V

    invoke-virtual {p0, v2}, Landroid/view/View;->setOnTouchListener(Landroid/view/View$OnTouchListener;)V

    const/4 v2, 0x4

    invoke-virtual {p0, v2}, Landroid/view/View;->setImportantForAccessibility(I)V

    :cond_done
    return-void
.end method
