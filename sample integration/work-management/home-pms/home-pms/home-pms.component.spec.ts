import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HomePmsComponent } from './home-pms.component';

describe('HomePmsComponent', () => {
  let component: HomePmsComponent;
  let fixture: ComponentFixture<HomePmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ HomePmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HomePmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
